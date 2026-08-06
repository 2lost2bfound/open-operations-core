"""Platform registry — manages cross-platform skill installation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .adapters.base import PlatformAdapter
from .adapters.native import NativeAdapter
from .adapters.cursor import CursorAdapter
from .adapters.windsurf import WindsurfAdapter


class PlatformRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        native_platforms = [
            "claude-code", "codex", "opencode", "cline", "aider",
            "copilot", "trae", "kiro", "amp", "goose",
        ]
        for platform in native_platforms:
            self._adapters[platform] = NativeAdapter(platform)
        self._adapters["cursor"] = CursorAdapter()
        self._adapters["windsurf"] = WindsurfAdapter()

    def get(self, name: str) -> PlatformAdapter | None:
        return self._adapters.get(name)

    def list_platforms(self) -> list[str]:
        return sorted(self._adapters.keys())

    def register(self, name: str, adapter: PlatformAdapter) -> None:
        self._adapters[name] = adapter
