"""CLI entry point — Click-based command interface."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import click

from .config import SSGConfig
from .pipeline import PipelineEngine
from .crawler import CrawlEngine
from .quality import SkillValidator, SecurityScanner


@contextmanager
def secure_temporary_directory() -> Iterator[Path]:
    """Yield a crawl workspace that is private to the current user."""
    path = Path(tempfile.mkdtemp(prefix="ssg-reverse-"))
    path.chmod(0o700)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@click.group()
@click.option("--config", "-c", type=click.Path(exists=False), default=None, help="Path to ssg.toml")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, config: str | None, verbose: bool) -> None:
    """ssg — Super-Skill Generator CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = SSGConfig.load(Path(config) if config else None)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.argument("description")
@click.option("--name", "-n", default=None, help="Skill name override")
@click.option("--output", "-o", default=None, help="Output directory")
@click.pass_context
def create(ctx: click.Context, description: str, name: str | None, output: str | None) -> None:
    """Create a skill from a natural-language description."""
    cfg: SSGConfig = ctx.obj["config"]
    skill_name = name or cfg.project_name
    out_dir = Path(output or cfg.output_dir)
    engine = PipelineEngine(cfg)
    result = engine.run(description, skill_name, out_dir)
    if result.success:
        click.echo(f"Skill '{skill_name}' created at {result.output_path}")
    else:
        click.echo(f"Pipeline failed: {result.error}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("--output", "-o", default=None, help="Output directory")
@click.option("--flat", is_flag=True, help="Flat file structure")
@click.option("--depth", "-d", default=None, type=int, help="Max crawl depth")
@click.pass_context
def crawl(ctx: click.Context, urls: tuple[str, ...], output: str | None, flat: bool, depth: int | None) -> None:
    """Crawl documentation URLs into Markdown skill references."""
    cfg: SSGConfig = ctx.obj["config"]
    out_dir = Path(output or cfg.crawl.output_dir)
    if depth is not None:
        cfg.crawl.max_depth = depth
    if flat:
        cfg.crawl.flat = True
    engine = CrawlEngine(cfg.crawl)
    results = engine.crawl_all(list(urls), out_dir)
    click.echo(f"Crawled {len(results)} pages to {out_dir}")
    for r in results:
        click.echo(f"  {r.url} -> {r.output_path}")


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.pass_context
def validate(ctx: click.Context, skill_path: str) -> None:
    """Validate a generated skill against quality standards."""
    cfg: SSGConfig = ctx.obj["config"]
    validator = SkillValidator(cfg.quality)
    report = validator.validate(Path(skill_path))
    click.echo(report.summary())
    if not report.passed:
        sys.exit(1)


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.pass_context
def security(ctx: click.Context, skill_path: str) -> None:
    """Run security scan on a skill."""
    scanner = SecurityScanner()
    report = scanner.scan(Path(skill_path))
    click.echo(report.summary())
    if report.severity == "critical":
        sys.exit(1)


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.option("--platform", "-p", multiple=True, help="Target platforms")
@click.pass_context
def install(ctx: click.Context, skill_path: str, platform: tuple[str, ...]) -> None:
    """Install a skill to agent platform directories."""
    from .platforms import PlatformRegistry

    cfg: SSGConfig = ctx.obj["config"]
    targets = list(platform) if platform else cfg.platforms
    registry = PlatformRegistry()
    for target in targets:
        adapter = registry.get(target)
        if adapter is None:
            click.echo(f"Unknown platform: {target}", err=True)
            continue
        adapter.install(Path(skill_path))
        click.echo(f"Installed to {target}")


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
@click.pass_context
def scan_deps(ctx: click.Context, skill_path: str) -> None:
    """Scan project dependencies and generate crawl rules."""
    from .crawler.deps import DependencyScanner

    scanner = DependencyScanner()
    rules = scanner.scan(Path(skill_path))
    click.echo(json.dumps([r.to_dict() for r in rules], indent=2))


@cli.command()
@click.argument("url")
@click.option("--name", "-n", default=None, help="Skill name override")
@click.option("--output", "-o", default=None, help="Output directory")
@click.option("--depth", "-d", default=2, type=int, help="Crawl depth (default 2)")
@click.option("--install-to", "-i", multiple=True, help="Auto-install to platforms")
@click.pass_context
def reverse(ctx: click.Context, url: str, name: str | None, output: str | None, depth: int, install_to: tuple[str, ...]) -> None:
    """Reverse-engineer a website into a skill. Crawls, analyzes, generates, validates."""
    from urllib.parse import urlparse

    cfg: SSGConfig = ctx.obj["config"]
    verbose: bool = ctx.obj["verbose"]
    out_dir = Path(output or cfg.output_dir)

    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    skill_name = name or domain.replace(".", "-")

    click.echo(f"Reverse-engineering {url} ...")

    # Step 1: Crawl
    click.echo(f"\n[1/4] Crawling (depth={depth}) ...")
    crawl_cfg = cfg.crawl
    crawl_cfg.max_depth = depth
    crawl_engine = CrawlEngine(crawl_cfg)
    with secure_temporary_directory() as crawl_path:
        results = crawl_engine.crawl_all([url], crawl_path)
        click.echo(f"  Crawled {len(results)} pages")
        if not results:
            click.echo("  No pages crawled. Check the URL and try again.", err=True)
            sys.exit(1)

        # Step 2: Build description from crawled content
        click.echo("\n[2/4] Analyzing content ...")
        combined = []
        for r in results:
            if r.output_path.exists():
                text = r.output_path.read_text(encoding="utf-8", errors="ignore")
                # Strip frontmatter
                if text.startswith("---"):
                    end = text.find("---", 3)
                    if end != -1:
                        text = text[end + 3:].strip()
                combined.append(f"## From {r.url}\n\n{text[:2000]}")
        crawled_content = "\n\n---\n\n".join(combined)
        first_page = combined[0].split("\n\n", 1)[-1] if combined else ""
        first_para = first_page.split("\n\n")[0][:200] if first_page else domain
        description = f"Skill for working with {domain}. {first_para}"
        if verbose:
            click.echo(f"  Built description from {len(combined)} pages ({len(crawled_content)} chars)")

    # Step 3: Generate skill
    click.echo(f"\n[3/4] Generating skill '{skill_name}' ...")
    engine = PipelineEngine(cfg)
    result = engine.run(description, skill_name, out_dir, source_url=url, crawled_content=crawled_content)
    if not result.success:
        click.echo(f"  Pipeline failed: {result.error}", err=True)
        sys.exit(1)
    click.echo(f"  Skill created at {result.output_path}")

    # Step 4: Validate
    click.echo("\n[4/4] Validating ...")
    validator = SkillValidator(cfg.quality)
    skill_md = result.output_path / "SKILL.md"
    if skill_md.exists():
        report = validator.validate(skill_md)
        click.echo(f"  {report.summary()}")
    else:
        click.echo("  SKILL.md not found, skipping validation")

    # Optional: auto-install
    if install_to:
        from .platforms import PlatformRegistry
        registry = PlatformRegistry()
        for target in install_to:
            adapter = registry.get(target)
            if adapter:
                adapter.install(result.output_path)
                click.echo(f"  Installed to {target}")
            else:
                click.echo(f"  Unknown platform: {target}", err=True)

    click.echo(f"\nDone. Skill at: {result.output_path}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
