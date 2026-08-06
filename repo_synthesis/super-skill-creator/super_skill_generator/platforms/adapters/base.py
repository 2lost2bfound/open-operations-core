"""Base adapter interface for platform installations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class PlatformAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def install(self, skill_path: Path) -> Path:
        ...

    @abstractmethod
    def get_install_dir(self) -> Path:
        ...
