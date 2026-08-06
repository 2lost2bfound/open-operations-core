"""Crawl engine — recursive web crawler with incremental support."""

from __future__ import annotations

import re
import ipaddress
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from parsel import Selector
import yaml

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
            follow_redirects=False,
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
        if depth > self.config.max_depth or url in self.visited or len(self.visited) >= self.config.max_pages:
            return []
        self._validate_url(url)
        self.visited.add(url)
        results: list[CrawlResult] = []
        try:
            existing_md = self._find_existing(url, output_dir)
            headers = {}
            if existing_md:
                mod_date = self._read_last_modified(existing_md)
                if mod_date:
                    headers["If-Modified-Since"] = mod_date
            fetched = self._fetch(url, headers)
            if fetched is None:
                return []
            final_url, status_code, response_headers, body = fetched
            if final_url != url:
                self.visited.add(final_url)
            if status_code == 304:
                return []
            if status_code != 200:
                return []
            content_type = response_headers.get("content-type", "")
            if "text/html" in content_type:
                html = body.decode(response_headers.get("content-type", "").split("charset=")[-1].strip(" ;") or "utf-8", errors="replace")
                result = self._process_html(final_url, html, output_dir)
                if result:
                    results.append(result)
                links = self._extract_links(html, final_url)
                for link in links:
                    results.extend(self._crawl(link, output_dir, depth + 1))
        except (httpx.HTTPError, ValueError, socket.gaierror):
            pass
        return results

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("crawler only permits http and https URLs")
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("crawler URL must have a host and no embedded credentials")
        if self.config.allow_private_network:
            return
        try:
            addresses = {
                info[4][0]
                for info in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            }
        except socket.gaierror as exc:
            raise ValueError("crawler host could not be resolved") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise ValueError("crawler blocks private, loopback, link-local, and reserved addresses by default")

    def _fetch(self, url: str, headers: dict[str, str]) -> tuple[str, int, httpx.Headers, bytes] | None:
        current = url
        for _ in range(10):
            self._validate_url(current)
            with self._client.stream("GET", current, headers=headers) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        return None
                    current = urljoin(current, location)
                    continue
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.config.max_response_bytes:
                    return None
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self.config.max_response_bytes:
                        return None
                    chunks.append(chunk)
                return current, response.status_code, response.headers, b"".join(chunks)
        return None

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
                    try:
                        self._validate_url(clean)
                    except (ValueError, socket.gaierror):
                        continue
                    links.append(clean)
        return links[:50]

    def _build_frontmatter(self, metadata: dict[str, str]) -> str:
        clean = {key: value for key, value in metadata.items() if value}
        return "---\n" + yaml.safe_dump(clean, allow_unicode=True, sort_keys=False).rstrip() + "\n---"

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
