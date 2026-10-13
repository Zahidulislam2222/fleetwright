"""The exact payload, signer and signature must all match."""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.security.signing import sign_file, verify_file


def test_signature_rejects_tampered_payload_and_wrong_signer(tmp_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    wrong = tmp_path / "wrong.pem"
    payload, signature = tmp_path / "manifest.json", tmp_path / "manifest.sig"
    private.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    public.write_bytes(
        key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    wrong.write_bytes(
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    payload.write_bytes(b'{"sha256":"test-digest"}')
    sign_file(payload, private, signature)
    assert verify_file(payload, public, signature)
    assert not verify_file(payload, wrong, signature)
    payload.write_bytes(b'{"sha256":"tampered"}')
    assert not verify_file(payload, public, signature)
