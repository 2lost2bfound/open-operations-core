"""HTML to Markdown conversion using a parsed document tree."""

from __future__ import annotations

from html import unescape

from parsel import Selector


class HtmlToMarkdown:
    """Convert common documentation HTML without regex-parsing nested tags."""

    _BLOCK_TAGS = {"article", "div", "main", "section", "table", "tbody", "tr"}

    def convert(self, source: str) -> str:
        selector = Selector(text=source)
        bodies = selector.xpath("//body")
        root = bodies[0].root if bodies else selector.root
        rendered = self._render(root)
        rendered = unescape(rendered)
        lines = [line.rstrip() for line in rendered.splitlines()]
        result = "\n".join(lines)
        while "\n\n\n" in result:
            result = result.replace("\n\n\n", "\n\n")
        return result.strip()

    def _children(self, element) -> str:
        parts = [element.text or ""]
        for child in element:
            parts.append(self._render(child))
            parts.append(child.tail or "")
        return "".join(parts)

    def _render(self, element) -> str:
        tag = str(getattr(element, "tag", "")).lower()
        if tag in {"script", "style", "noscript", "template"}:
            return ""
        if tag in {"html", "head", "body"}:
            return self._children(element)
        if tag == "br":
            return "\n"
        if tag == "pre":
            raw = "".join(element.itertext()).strip("\n")
            return f"\n```\n{raw}\n```\n"

        inner = self._children(element)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            return f"\n{'#' * level} {inner.strip()}\n"
        if tag in {"strong", "b"}:
            return f"**{inner.strip()}**"
        if tag in {"em", "i"}:
            return f"*{inner.strip()}*"
        if tag == "code":
            return f"`{inner.strip()}`"
        if tag == "a":
            href = (element.get("href") or "").strip()
            label = inner.strip()
            return f"[{label}]({href})" if href else label
        if tag == "li":
            return f"\n- {inner.strip()}"
        if tag in self._BLOCK_TAGS or tag in {"p", "blockquote", "ul", "ol", "td", "th"}:
            return f"\n{inner.strip()}\n"
        return inner
