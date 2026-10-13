"""Authenticated off-host recovery bundles. No secret is stored inside its own recovery bundle."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path
from uuid import uuid4

from fw_core.crypto import NONCE_BYTES, Envelope, Sealed
from fw_core.settings import RecoverySettings

FORMAT = b"FWRECOVERY1\n"
AAD = b"fleetwright-offhost-recovery-v1"


def validate(files: dict[str, bytes], limit: int) -> None:
    if "manifest.json" not in files or sum(map(len, files.values())) > limit:
        raise ValueError("missing manifest or archive size limit exceeded")
    try:
        metadata = json.loads(files["manifest.json"])
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid archive manifest") from exc
    if not isinstance(metadata, dict):
        raise ValueError("invalid archive manifest")
    databases = metadata.get("databases", {})
    expected = {"manifest.json"}
    if not isinstance(databases, dict) or not databases:
        raise ValueError("empty archive manifest")
    for database, entry in databases.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,62}", database):
            raise ValueError("invalid database name")
        if (
            not isinstance(entry, dict)
            or type(entry.get("bytes")) is not int
            or entry["bytes"] <= 0
            or not isinstance(entry.get("sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"])
        ):
            raise ValueError("invalid archive integrity record")
        name = database + ".dump"
        expected.add(name)
        data = files.get(name, b"")
        if (
            not data.startswith(b"PGDMP")
            or len(data) != entry["bytes"]
            or hashlib.sha256(data).hexdigest() != entry["sha256"]
        ):
            raise ValueError("archive integrity failure")
    if set(files) != expected:
        raise ValueError("unexpected recovery files")


def protect(cfg: RecoverySettings, files: dict[str, bytes]) -> Path:
    validate(files, cfg.max_archive_bytes)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    sealed = Envelope(cfg.master_key_b64.get_secret_value(), cfg.key_id).seal(buffer.getvalue(), AAD)
    header = json.dumps(
        {
            "key_id": sealed.key_id,
            "wrapped_key": base64.b64encode(sealed.wrapped_key).decode(),
            "nonce": base64.b64encode(sealed.nonce).decode(),
        },
        separators=(",", ":"),
    ).encode()
    cfg.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if cfg.directory.is_symlink():
        raise ValueError("recovery directory must not be a symlink")
    target = cfg.directory / (uuid4().hex + ".fwrecovery")
    temporary = target.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(FORMAT + len(header).to_bytes(4, "big") + header + sealed.ciphertext)
        output.flush()
        os.fsync(output.fileno())
    # Verify the exact ciphertext before publication or pruning any older copy.
    recovered = open_bundle(cfg, temporary)
    if recovered != files:
        raise ValueError("encrypted recovery verification failed")
    os.replace(temporary, target)
    completed = sorted(
        (p for p in cfg.directory.glob("*.fwrecovery") if not p.is_symlink()), key=lambda p: p.stat().st_mtime
    )
    for old in completed[: -cfg.retention_count]:
        old.unlink()
    return target


def open_bundle(cfg: RecoverySettings, source: Path) -> dict[str, bytes]:
    if source.is_symlink() or source.stat().st_size > cfg.max_archive_bytes + 65536:
        raise ValueError("unsafe or oversized recovery bundle")
    with source.open("rb") as stream:
        if stream.read(len(FORMAT)) != FORMAT:
            raise ValueError("unsupported recovery format")
        header_size = int.from_bytes(stream.read(4), "big")
        if not 0 < header_size <= 4096:
            raise ValueError("invalid recovery header")
        header_data = stream.read(header_size)
        if len(header_data) != header_size:
            raise ValueError("truncated recovery header")
        header = json.loads(header_data)
        if not isinstance(header, dict) or set(header) != {"key_id", "wrapped_key", "nonce"}:
            raise ValueError("invalid recovery metadata")
        if not isinstance(header["key_id"], str) or any(
            not isinstance(header[key], str) for key in ("wrapped_key", "nonce")
        ):
            raise ValueError("invalid recovery metadata types")
        sealed = Sealed(
            header["key_id"],
            base64.b64decode(header["wrapped_key"], validate=True),
            base64.b64decode(header["nonce"], validate=True),
            stream.read(),
        )
        # AES-256 data key (32 bytes) and AES-GCM tag (16 bytes) are format invariants.
        if (
            len(sealed.nonce) != NONCE_BYTES
            or len(sealed.wrapped_key) != NONCE_BYTES + 32 + 16
            or len(sealed.ciphertext) < 16
        ):
            raise ValueError("invalid recovery envelope lengths")
    plaintext = Envelope(cfg.master_key_b64.get_secret_value(), cfg.key_id).open(sealed, AAD)
    with zipfile.ZipFile(io.BytesIO(plaintext)) as archive:
        entries = archive.infolist()
        if len(entries) != len({entry.filename for entry in entries}):
            raise ValueError("duplicate archive entry")
        if sum(entry.file_size for entry in entries) > cfg.max_archive_bytes:
            raise ValueError("expanded archive size limit")
        if any(entry.compress_type != zipfile.ZIP_STORED for entry in entries):
            raise ValueError("compressed recovery entries are unsupported")
        files = {entry.filename: archive.read(entry) for entry in entries}
    validate(files, cfg.max_archive_bytes)
    return files


def unpack(cfg: RecoverySettings, source: Path, destination: Path) -> Path:
    files = open_bundle(cfg, source)
    # Never extract archive paths; validate() permits only exact safe database filenames.
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in files.items():
        descriptor = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
    return destination
