"""Metadata extractor — pulls structured data from HTML pages."""

from __future__ import annotations

from datetime import datetime, timezone

from parsel import Selector


class MetadataExtractor:
    def extract(self, selector: Selector, url: str) -> dict[str, str]:
        title = (
            selector.css("meta[property='og:title']::attr(content)").get()
            or selector.css("title::text").get()
            or ""
        )
        description = (
            selector.css("meta[property='og:description']::attr(content)").get()
            or selector.css("meta[name='description']::attr(content)").get()
            or ""
        )
        last_modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "name": self._sanitize_name(title or url.split("/")[-1]),
            "description": self._sanitize_description(description),
            "metadata.url": url,
            "metadata.last_modified": last_modified,
        }

    def _sanitize_name(self, text: str) -> str:
        import re
        name = re.sub(r"[^\w\s-]", "", text.lower())
        name = re.sub(r"[\s_]+", "-", name)
        return name[:64].strip("-")

    def _sanitize_description(self, text: str) -> str:
        text = " ".join(text.split())
        return text[:1024]
