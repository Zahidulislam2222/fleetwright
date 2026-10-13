"""Inventory provenance must exclude private files, symlinks and configured generated trees."""

import hashlib
from pathlib import Path

from tools.security.assurance import manifest


def test_manifest_hashes_source_and_refuses_secret_paths(tmp_path: Path) -> None:
    (tmp_path / "source.py").write_text("print('public')")
    (tmp_path / ".env").write_text("FAKE_TOKEN=test-key")
    (tmp_path / "CREDENTIALS.md").write_text("test-key")
    (tmp_path / "private.key").write_text("test-key")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "large.js").write_text("ignored")
    result = manifest([tmp_path], {"node_modules"})
    assert result == {(tmp_path / "source.py").as_posix(): hashlib.sha256(b"print('public')").hexdigest()}
