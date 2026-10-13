"""POSIX state privacy tests also run directly with stdlib unittest, without service dependencies."""

from __future__ import annotations

import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from fw_agent.privacy import private_directory, private_file


@unittest.skipUnless(os.name == "posix", "POSIX modes do not describe Windows inherited ACLs")
class PrivateStateTests(unittest.TestCase):
    def test_database_and_wal_remain_private_under_permissive_umask(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "state"
            previous = os.umask(0o022)
            try:
                database = directory / "agent.sqlite"
                private_file(database)
                with sqlite3.connect(database) as connection:
                    connection.execute("PRAGMA journal_mode=WAL")
                    connection.execute("CREATE TABLE evidence(value TEXT)")
                    connection.execute("INSERT INTO evidence VALUES('test-data')")
                    connection.commit()
                    self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
                    for filename in (database.name, database.name + "-wal", database.name + "-shm"):
                        self.assertEqual(stat.S_IMODE((directory / filename).stat().st_mode), 0o600)
            finally:
                os.umask(previous)

    def test_existing_profile_and_evidence_are_hardened_without_losing_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "profile"
            profile.mkdir(mode=0o755)
            evidence = profile / "receipt.json"
            evidence.write_text("test receipt", encoding="utf-8")
            evidence.chmod(0o644)
            private_directory(profile)
            private_file(evidence)
            self.assertEqual(evidence.read_text(encoding="utf-8"), "test receipt")
            self.assertEqual(stat.S_IMODE(profile.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(evidence.stat().st_mode), 0o600)

    def test_symlink_database_refused_without_modifying_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "other-user-data"
            target.write_text("untouched", encoding="utf-8")
            target.chmod(0o644)
            link = root / "agent.sqlite"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                private_file(link)
            self.assertEqual(target.read_text(encoding="utf-8"), "untouched")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_symlink_parent_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "destination"
            target.mkdir()
            link = root / "state"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(ValueError):
                private_file(link / "agent.sqlite")
            self.assertFalse((target / "agent.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
