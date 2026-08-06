"""Crawl engine — recursive web crawler with incremental support."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from parsel import Selector

from ..config import CrawlConfig
from .html_to_md import HtmlToMarkdown
from .metadata import MetadataExtractor


@dataclass
class CrawlResult:
    url: str
    output_path: Path
    status: int
    content_type: str = "text/html"


class CrawlEngine:
    def __init__(self, config: CrawlConfig) -> None:
        self.config = config
        self.visited: set[str] = set()
        self.converter = HtmlToMarkdown()
        self.extractor = MetadataExtractor()
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": config.user_agent},
        )

    def crawl_all(self, urls: list[str], output_dir: Path) -> list[CrawlResult]:
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[CrawlResult] = []
        for url in urls:
            results.extend(self._crawl(url, output_dir, depth=0))
        self._client.close()
        return results

    def _crawl(self, url: str, output_dir: Path, depth: int) -> list[CrawlResult]:
        if depth > self.config.max_depth or url in self.visited:
            return []
        self.visited.add(url)
        results: list[CrawlResult] = []
        try:
            existing_md = self._find_existing(url, output_dir)
            headers = {}
            if existing_md:
                mod_date = self._read_last_modified(existing_md)
                if mod_date:
                    headers["If-Modified-Since"] = mod_date
            resp = self._client.get(url, headers=headers)
            if resp.status_code == 304:
                return []
            if resp.status_code != 200:
                return []
            content_type = resp.headers.get("content-type", "")
            if "text/html" in content_type:
                result = self._process_html(url, resp.text, output_dir)
                if result:
                    results.append(result)
                links = self._extract_links(resp.text, url)
                for link in links:
                    results.extend(self._crawl(link, output_dir, depth + 1))
        except httpx.HTTPError:
            pass
        return results

    def _process_html(self, url: str, html: str, output_dir: Path) -> CrawlResult | None:
        selector = Selector(text=html)
        metadata = self.extractor.extract(selector, url)
        content_html = self._extract_content(selector)
        markdown = self.converter.convert(content_html)
        frontmatter = self._build_frontmatter(metadata)
        full_content = frontmatter + "\n" + markdown
        output_path = self._get_output_path(url, output_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(full_content, encoding="utf-8")
        return CrawlResult(url=url, output_path=output_path, status=200)

    def _extract_content(self, selector: Selector) -> str:
        for tag in selector.css("script, style, nav, footer, header"):
            tag.root.getparent().remove(tag.root)
        article = selector.css("article").get()
        if article:
            return article
        main = selector.css("main").get()
        if main:
            return main
        body = selector.css("body").get()
        return body or ""

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        selector = Selector(text=html)
        links = []
        base_domain = urlparse(base_url).netloc
        for href in selector.css("a::attr(href)").getall():
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            if parsed.netloc == base_domain and full_url not in self.visited:
                clean = full_url.split("#")[0]
                if clean and not any(
                    clean.endswith(ext)
                    for ext in [".pdf", ".zip", ".tar", ".gz", ".png", ".jpg"]
                ):
                    links.append(clean)
        return links[:50]

    def _build_frontmatter(self, metadata: dict[str, str]) -> str:
        lines = ["---"]
        for key, value in metadata.items():
            if value:
                safe = value.replace('"', '\\"')
                lines.append(f'{key}: "{safe}"')
        lines.append("---")
        return "\n".join(lines)

    def _get_output_path(self, url: str, output_dir: Path) -> Path:
        parsed = urlparse(url)
        if self.config.flat:
            safe = re.sub(r"[^\w]", "_", parsed.path.strip("/"))[:64]
            name = f"{parsed.netloc}_{safe}" if safe else parsed.netloc
            return output_dir / f"{name}.md"
        parts = [parsed.netloc] + [p for p in parsed.path.split("/") if p]
        if not parts[-1].endswith(".md"):
            parts[-1] = parts[-1] + ".md" if "." not in parts[-1] else parts[-1]
        return output_dir / Path(*parts)

    def _find_existing(self, url: str, output_dir: Path) -> Path | None:
        path = self._get_output_path(url, output_dir)
        return path if path.exists() else None

    def _read_last_modified(self, path: Path) -> str | None:
        text = path.read_text(encoding="utf-8", errors="ignore")[:500]
        match = re.search(r"last_modified:\s*\"?([^\"]+?)\"?\s*$", text, re.MULTILINE)
        return match.group(1) if match else None
