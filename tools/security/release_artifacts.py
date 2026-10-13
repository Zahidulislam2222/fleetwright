"""Sign and verify an exact release inventory with the owner's independent Ed25519 identity.

MANIFEST covers all files except itself. Signed provenance covers primary artifacts and the bundled
public key, excluding only the manifest/provenance/signature control files to avoid circular hashes.
Verification requires a separately trusted public key, never trust in the bundle's own key alone.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fw_core.settings import ReleaseSigningAppSettings, ReleaseSigningSettings, load
from tools.security.signing import ignored, sign_file, verify_file

# Authoritative release format names and hash syntax are protocol definitions, not environment config.
MANIFEST = "MANIFEST.sha256"
PROVENANCE = "PROVENANCE.json"
SIGNATURE = "PROVENANCE.sig"
PUBLIC_KEY = "RELEASE-SIGNING-PUBLIC.pem"
SBOM = "SBOM.cdx.json"
FORMAT = "fleetwright-release-provenance-v1"
CONTROL = frozenset({MANIFEST, PROVENANCE, SIGNATURE})
HEX_DIGEST = re.compile(r"[a-f0-9]{64}")
IMAGE_IDENTITY = re.compile(r"(?:[^\s@]+@)?sha256:[a-f0-9]{64}")


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and bool(path.parts)
        and (
            not path.is_absolute()
            and path.as_posix() == name
            and all(part not in (".", "..") for part in path.parts)
            and not any(ord(char) < 32 or char in "\\:" for char in name)
        )
    )


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1 << 20):
            result.update(block)
    return result.hexdigest()


def inventory(root: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("release must be a regular directory")
    files = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("release symlinks are forbidden")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("non-regular release entry")
        name = path.relative_to(root).as_posix()
        if not safe_name(name):
            raise ValueError("unsafe release path")
        files[name] = digest(path)
    return files


def manifest_bytes(files: dict[str, str]) -> bytes:
    return "".join(f"{value}  {name}\n" for name, value in sorted(files.items()) if name != MANIFEST).encode()


def read_manifest(root: Path) -> dict[str, str]:
    try:
        text = (root / MANIFEST).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("missing or invalid release manifest") from exc
    files = {}
    for line in text.splitlines():
        if len(line) < 67 or line[64:66] != "  " or not HEX_DIGEST.fullmatch(line[:64]):
            raise ValueError("invalid release manifest record")
        name = line[66:]
        if not safe_name(name) or name in files or name == MANIFEST:
            raise ValueError("unsafe or duplicate release manifest record")
        files[name] = line[:64]
    if not files:
        raise ValueError("empty release manifest")
    return files


def release_metadata(root: Path) -> tuple[str, str]:
    try:
        data = json.loads((root / "RELEASE.json").read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError("missing or malformed release metadata") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid release metadata")
    release, commit = data.get("releaseId"), data.get("commit")
    if not isinstance(release, str) or not re.fullmatch(r"\d{8}-[a-z0-9-]+", release):
        raise ValueError("invalid release identity")
    if not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", commit):
        raise ValueError("invalid source commit")
    return release, commit


def verify(root: Path, trusted_public_key: Path) -> dict[str, Any]:
    if trusted_public_key.resolve().is_relative_to(root.resolve()):
        raise ValueError("verification key must be trusted independently outside the release")
    actual = inventory(root)
    required = {MANIFEST, PROVENANCE, SIGNATURE, PUBLIC_KEY, "RELEASE.json", "src.tar"}
    if not required <= actual.keys():
        raise ValueError("missing signed release artifact")
    if (root / PUBLIC_KEY).read_bytes() != trusted_public_key.read_bytes():
        raise ValueError("bundled signer does not match separately trusted public key")
    try:
        valid = verify_file(root / PROVENANCE, trusted_public_key, root / SIGNATURE)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("invalid release signature") from exc
    if not valid:
        raise ValueError("invalid release signature")
    try:
        provenance = json.loads((root / PROVENANCE).read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError("invalid provenance document") from exc
    if not isinstance(provenance, dict) or provenance.get("format") != FORMAT:
        raise ValueError("unsupported release provenance")
    expected_artifacts = {name: value for name, value in actual.items() if name not in CONTROL}
    if provenance.get("artifacts") != expected_artifacts:
        raise ValueError("signed artifact inventory mismatch")
    release, commit = release_metadata(root)
    if provenance.get("release_id") != release or provenance.get("source_commit") != commit:
        raise ValueError("signed release metadata mismatch")
    image = provenance.get("image_identity")
    if image is not None and (not isinstance(image, str) or not IMAGE_IDENTITY.fullmatch(image)):
        raise ValueError("invalid signed image identity")
    sbom = provenance.get("sbom")
    if sbom is not None and (sbom != SBOM or SBOM not in expected_artifacts):
        raise ValueError("invalid signed SBOM reference")
    if read_manifest(root) != {name: value for name, value in actual.items() if name != MANIFEST}:
        raise ValueError("complete release manifest mismatch")
    if (root / MANIFEST).read_bytes() != manifest_bytes(actual):
        raise ValueError("release manifest is not canonical")
    return provenance


def finalize(
    root: Path, cfg: ReleaseSigningSettings, image_identity: str | None = None, sbom: Path | None = None
) -> dict[str, Any]:
    """Finalize only an unsigned, already-hash-verified release. CLI additionally requires ignored key."""
    before = inventory(root)
    if {PROVENANCE, SIGNATURE, PUBLIC_KEY} & before.keys():
        raise ValueError("release already signed or partially finalized; use a new immutable release")
    if not {MANIFEST, "RELEASE.json", "src.tar"} <= before.keys():
        raise ValueError("missing primary release artifact")
    if read_manifest(root) != {name: value for name, value in before.items() if name != MANIFEST}:
        raise ValueError("unsigned primary manifest mismatch")
    if image_identity is not None and not IMAGE_IDENTITY.fullmatch(image_identity):
        raise ValueError("image identity must be an immutable SHA-256 ID or repository digest")
    if cfg.private_key_file.resolve().is_relative_to(root.resolve()) or cfg.private_key_file.is_symlink():
        raise ValueError("private signer must be a regular file outside release artifacts")
    if cfg.public_key_file.resolve().is_relative_to(root.resolve()):
        raise ValueError("public trust anchor must remain independently outside release artifacts")
    key = serialization.load_pem_private_key(cfg.private_key_file.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("release signer must be Ed25519")
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    if cfg.public_key_file.read_bytes() != public:
        raise ValueError("private signer does not match configured public key; rotation refused")
    release, commit = release_metadata(root)
    additions = {PUBLIC_KEY: public}
    if sbom is not None:
        if SBOM in before:
            raise ValueError("SBOM artifact already exists; ambiguous replacement refused")
        data = sbom.read_bytes()
        try:
            metadata = json.loads(data)
        except ValueError as exc:
            raise ValueError("SBOM must be CycloneDX JSON") from exc
        if not isinstance(metadata, dict) or metadata.get("bomFormat") != "CycloneDX":
            raise ValueError("SBOM must be CycloneDX JSON")
        additions[SBOM] = data
    artifacts = {name: value for name, value in before.items() if name != MANIFEST}
    artifacts.update({name: hashlib.sha256(data).hexdigest() for name, data in additions.items()})
    provenance = {
        "format": FORMAT,
        "key_id": cfg.key_id,
        "release_id": release,
        "source_commit": commit,
        "image_identity": image_identity,
        "image_identity_kind": "caller_inspected_immutable_image" if image_identity else None,
        "sbom": SBOM if sbom is not None else None,
        "artifacts": dict(sorted(artifacts.items())),
    }
    payload = (json.dumps(provenance, sort_keys=True, indent=2) + "\n").encode()
    with tempfile.TemporaryDirectory(prefix="fleetwright-sign-") as temporary:
        staging = Path(temporary)
        (staging / PROVENANCE).write_bytes(payload)
        sign_file(staging / PROVENANCE, cfg.private_key_file, staging / SIGNATURE)
        if not verify_file(staging / PROVENANCE, cfg.public_key_file, staging / SIGNATURE):
            raise ValueError("new signature verification failed")
        additions[PROVENANCE] = payload
        additions[SIGNATURE] = (staging / SIGNATURE).read_bytes()
        if inventory(root) != before:
            raise ValueError("primary release changed during signing")
        for name, data in additions.items():
            (staging / name).write_bytes(data)
            # Staging may be on another filesystem; copy into an exclusive sibling before replace.
            temporary_file = root / (name + ".new")
            descriptor = os.open(temporary_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_file, root / name)
    final_inventory = inventory(root)
    expected = dict(before)
    expected.update({name: hashlib.sha256(data).hexdigest() for name, data in additions.items()})
    if final_inventory != expected:
        raise ValueError("release changed during finalization")
    temporary_manifest = root / (MANIFEST + ".new")
    descriptor = os.open(temporary_manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as output:
        output.write(manifest_bytes(final_inventory))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary_manifest, root / MANIFEST)
    return verify(root, cfg.public_key_file)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("sign", "verify"))
    parser.add_argument("release", type=Path)
    parser.add_argument("--image-identity")
    parser.add_argument("--sbom", type=Path)
    args = parser.parse_args()
    cfg = load(ReleaseSigningAppSettings).release_signing
    if args.operation == "sign":
        if not await ignored(cfg.private_key_file):
            raise RuntimeError("private release signer must be gitignored")
        result = await asyncio.to_thread(finalize, args.release, cfg, args.image_identity, args.sbom)
    else:
        result = await asyncio.to_thread(verify, args.release, cfg.public_key_file)
    print(
        json.dumps(
            {
                "status": "PASS",
                "release_id": result["release_id"],
                "source_commit": result["source_commit"],
                "artifacts": len(result["artifacts"]),
                "signature": "Ed25519 with separately trusted configured public key",
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
