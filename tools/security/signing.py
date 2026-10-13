"""Offline Ed25519 detached signatures for exact release/provenance bytes.

The owner holds the ignored private key. Public verification keys are safe package data.
This establishes a local signer identity only; it is not third-party/SLSA certification.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


async def ignored(path: Path) -> bool:
    process = await asyncio.create_subprocess_exec("git", "check-ignore", "--quiet", str(path))
    return await process.wait() == 0


def sign_file(payload: Path, private_file: Path, signature_file: Path) -> None:
    key = serialization.load_pem_private_key(private_file.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("release signing requires an Ed25519 private key")
    signature_file.write_bytes(base64.b64encode(key.sign(payload.read_bytes())))


def verify_file(payload: Path, public_file: Path, signature_file: Path) -> bool:
    key = serialization.load_pem_public_key(public_file.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("release verification requires an Ed25519 public key")
    try:
        key.verify(base64.b64decode(signature_file.read_bytes(), validate=True), payload.read_bytes())
    except (InvalidSignature, ValueError):
        return False
    return True


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("sign", "verify"))
    parser.add_argument("payload", type=Path)
    parser.add_argument("key_file", type=Path)
    parser.add_argument("signature_file", type=Path)
    args = parser.parse_args()
    if args.operation == "sign":
        if not await ignored(args.key_file):
            raise RuntimeError("private signing key must be gitignored before use")
        await asyncio.to_thread(sign_file, args.payload, args.key_file, args.signature_file)
        print("Detached Ed25519 signature written; verify with the separately protected public key.")
    else:
        if not await asyncio.to_thread(verify_file, args.payload, args.key_file, args.signature_file):
            raise SystemExit("signature verification failed")
        print("Detached Ed25519 signature verified for exact payload bytes.")


if __name__ == "__main__":
    asyncio.run(main())
