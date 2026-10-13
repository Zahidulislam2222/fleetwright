"""Owned state is private to the current OS user; symlinks are not state-file destinations."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _owned_without_symlinks(path: Path) -> None:
    for component in [path, *path.absolute().parents]:
        if component.is_symlink():
            raise ValueError("agent state paths must not contain symlinks")
    if sys.platform != "win32" and path.exists() and path.stat().st_uid != os.getuid():
        raise ValueError("agent state must belong to the current OS user")


def private_directory(path: Path) -> None:
    _owned_without_symlinks(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    _owned_without_symlinks(path)
    if os.name == "posix":
        path.chmod(0o700)


def private_file(path: Path) -> None:
    private_directory(path.parent)
    _owned_without_symlinks(path)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        if not path.is_file():
            raise ValueError("agent state destination must be a regular file") from None
    else:
        os.close(descriptor)
    restrict_existing_file(path)


def restrict_existing_file(path: Path) -> None:
    _owned_without_symlinks(path)
    if path.exists() and os.name == "posix":
        if not path.is_file():
            raise ValueError("agent state destination must be a regular file")
        path.chmod(0o600)
