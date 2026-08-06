"""Base adapter interface for platform installations."""

from __future__ import annotations

from abc import ABC, abstractmethod
import os
from pathlib import Path
import shutil
import tempfile
import uuid


def _backup_path(target: Path) -> Path:
    return target.with_name(f"{target.name}.backup-{uuid.uuid4().hex[:10]}")


def install_file(source: Path, target: Path, *, force: bool, dry_run: bool) -> Path:
    if target.exists() and not force:
        raise FileExistsError(f"Installation exists; rerun with --force to replace: {target}")
    if dry_run:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, staged_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(fd)
    staged = Path(staged_name)
    backup = None
    try:
        shutil.copy2(source, staged)
        if target.exists():
            backup = _backup_path(target)
            os.replace(target, backup)
        os.replace(staged, target)
    except Exception:
        staged.unlink(missing_ok=True)
        if backup and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    return target


def install_tree(source: Path, target: Path, *, force: bool, dry_run: bool) -> Path:
    if target.exists() and not force:
        raise FileExistsError(f"Installation exists; rerun with --force to replace: {target}")
    if dry_run:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    backup = None
    try:
        shutil.rmtree(staging)
        shutil.copytree(source, staging)
        if target.exists():
            backup = _backup_path(target)
            os.replace(target, backup)
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if backup and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    return target


class PlatformAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def install(self, skill_path: Path, *, force: bool = False, dry_run: bool = True) -> Path:
        ...

    @abstractmethod
    def get_install_dir(self) -> Path:
        ...
