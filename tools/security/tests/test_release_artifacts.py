"""Exact release inventory, trusted signer and every signed byte must match."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fw_core.settings import ReleaseSigningSettings
from tools.security.release_artifacts import finalize, verify


def fixtures(tmp_path: Path) -> tuple[Path, ReleaseSigningSettings]:
    release = tmp_path / "release"
    release.mkdir()
    (release / "dist").mkdir()
    (release / "dist/index.html").write_text("owned test release")
    (release / "src.tar").write_bytes(b"owned-source-archive")
    (release / "RELEASE.json").write_text(
        json.dumps(
            {
                "releaseId": "20261013-test",
                "commit": "a" * 40,
                "appImage": "owned-test:20261013-test",
            }
        )
    )
    hashes = {
        path.relative_to(release).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in release.rglob("*")
        if path.is_file()
    }
    (release / "MANIFEST.sha256").write_text(
        "".join(digest + "  " + name + "\n" for name, digest in sorted(hashes.items()))
    )
    key = Ed25519PrivateKey.generate()
    private, public = tmp_path / "test-private.pem", tmp_path / "test-public.pem"
    private.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    public.write_bytes(
        key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return release, ReleaseSigningSettings(private_key_file=private, public_key_file=public, key_id="test-signer")


def test_final_inventory_signature_and_sbom(tmp_path: Path) -> None:
    release, cfg = fixtures(tmp_path)
    sbom = tmp_path / "owned-sbom.json"
    sbom.write_text('{"bomFormat":"CycloneDX","specVersion":"1.6"}')
    finalize(release, cfg, "sha256:" + "b" * 64, sbom)
    info = verify(release, cfg.public_key_file)
    assert info["source_commit"] == "a" * 40
    assert info["image_identity"] == "sha256:" + "b" * 64
    assert info["artifacts"]["SBOM.cdx.json"] == hashlib.sha256(sbom.read_bytes()).hexdigest()
    manifest = (release / "MANIFEST.sha256").read_text()
    for name in ("PROVENANCE.json", "PROVENANCE.sig", "RELEASE-SIGNING-PUBLIC.pem"):
        assert name in manifest
    assert "MANIFEST.sha256" not in manifest


@pytest.mark.parametrize(
    "target", ["src.tar", "PROVENANCE.json", "PROVENANCE.sig", "MANIFEST.sha256", "RELEASE-SIGNING-PUBLIC.pem"]
)
def test_tampered_signed_release_rejected(tmp_path: Path, target: str) -> None:
    release, cfg = fixtures(tmp_path)
    finalize(release, cfg, "sha256:" + "b" * 64)
    with (release / target).open("ab") as output:
        output.write(b"changed")
    with pytest.raises(ValueError):
        verify(release, cfg.public_key_file)


@pytest.mark.parametrize("change", ["extra", "missing", "unsigned_manifest_rewrite"])
def test_complete_file_list_is_enforced(tmp_path: Path, change: str) -> None:
    release, cfg = fixtures(tmp_path)
    finalize(release, cfg, "sha256:" + "b" * 64)
    if change == "extra":
        (release / "unlisted.txt").write_text("extra")
    elif change == "missing":
        (release / "src.tar").unlink()
    else:
        (release / "MANIFEST.sha256").write_text("")
    with pytest.raises(ValueError):
        verify(release, cfg.public_key_file)


def test_wrong_trusted_key_and_resigning_refused(tmp_path: Path) -> None:
    release, cfg = fixtures(tmp_path)
    finalize(release, cfg, "sha256:" + "b" * 64)
    wrong = tmp_path / "wrong-public.pem"
    wrong.write_bytes(
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    with pytest.raises(ValueError):
        verify(release, wrong)
    with pytest.raises(ValueError):
        finalize(release, cfg, "sha256:" + "b" * 64)


def test_primary_manifest_drift_refused_before_signing(tmp_path: Path) -> None:
    release, cfg = fixtures(tmp_path)
    (release / "src.tar").write_text("changed before signing")
    with pytest.raises(ValueError):
        finalize(release, cfg, "sha256:" + "b" * 64)
    assert not (release / "PROVENANCE.json").exists()


def test_duplicate_and_unsafe_manifest_paths_refused(tmp_path: Path) -> None:
    release, cfg = fixtures(tmp_path)
    for name in ("../outside", "dist/../src.tar", "dist\\index.html", "/absolute"):
        (release / "MANIFEST.sha256").write_text("a" * 64 + "  " + name + "\n")
        with pytest.raises(ValueError):
            finalize(release, cfg, "sha256:" + "b" * 64)
    row = "a" * 64 + "  src.tar\n"
    (release / "MANIFEST.sha256").write_text(row + row)
    with pytest.raises(ValueError):
        finalize(release, cfg, "sha256:" + "b" * 64)


def test_bundle_cannot_supply_its_own_trust_anchor(tmp_path: Path) -> None:
    release, cfg = fixtures(tmp_path)
    finalize(release, cfg, "sha256:" + "b" * 64)
    with pytest.raises(ValueError):
        verify(release, release / "RELEASE-SIGNING-PUBLIC.pem")


def test_symlink_artifacts_are_rejected(tmp_path: Path) -> None:
    release, cfg = fixtures(tmp_path)
    finalize(release, cfg, "sha256:" + "b" * 64)
    alias = release / "alias.txt"
    try:
        alias.symlink_to("src.tar")
    except OSError:
        pytest.skip("Windows account lacks symlink privilege")
    with pytest.raises(ValueError):
        verify(release, cfg.public_key_file)
