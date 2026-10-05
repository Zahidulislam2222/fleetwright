"""Envelope encryption for the session vault and stored target-site credentials.

Each record gets its own random data key (AES-256-GCM). The data key is wrapped with the master key.
The associated data binds a ciphertext to its row (tenant + account + purpose), so a ciphertext copied
into another row fails to decrypt. On AWS the master-key wrap moves to KMS without changing callers.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12  # AES-GCM standard nonce size


@dataclass(frozen=True)
class Sealed:
    key_id: str
    wrapped_key: bytes  # nonce + AESGCM(master).encrypt(data key)
    nonce: bytes
    ciphertext: bytes


class Envelope:
    def __init__(self, master_key_b64: str, key_id: str) -> None:
        key = base64.b64decode(master_key_b64, validate=True)
        if len(key) != 32:
            raise ValueError("vault master key must be 32 bytes (base64)")
        self._master = AESGCM(key)
        self.key_id = key_id

    def seal(self, plaintext: bytes, aad: bytes) -> Sealed:
        dek = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)
        wrap_nonce = os.urandom(NONCE_BYTES)
        wrapped = wrap_nonce + self._master.encrypt(wrap_nonce, dek, b"dek|" + aad)
        return Sealed(self.key_id, wrapped, nonce, ciphertext)

    def open(self, sealed: Sealed, aad: bytes) -> bytes:
        if sealed.key_id != self.key_id:
            raise ValueError(f"record sealed with key {sealed.key_id}, vault has {self.key_id}")
        wrap_nonce, wrapped = sealed.wrapped_key[:NONCE_BYTES], sealed.wrapped_key[NONCE_BYTES:]
        dek = self._master.decrypt(wrap_nonce, wrapped, b"dek|" + aad)
        return AESGCM(dek).decrypt(sealed.nonce, sealed.ciphertext, aad)


def aad_for(tenant_id: object, account_id: object, purpose: str) -> bytes:
    return f"{tenant_id}|{account_id}|{purpose}".encode()
