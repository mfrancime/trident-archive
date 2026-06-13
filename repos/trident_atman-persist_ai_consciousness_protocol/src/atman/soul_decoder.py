"""
Soul Decoder — Retrieves and decrypts soul from encrypted payload.

Reverses the SoulEncoder pipeline:
encrypted bytes → AES-256-GCM decrypt → zlib decompress → JSON → Soul
"""

from __future__ import annotations

import json
import zlib
from dataclasses import fields

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from atman.soul_encoder import Soul, SoulEncoder, SoulFragment


class SoulDecodeError(Exception):
    """Raised when soul decoding fails."""


class SoulDecoder:
    """
    Decodes encrypted soul payloads back into Soul objects.

    Validates magic bytes, version, and AEAD authentication tag
    to ensure soul integrity before reconstruction.
    """

    def __init__(self, decryption_key: bytes):
        """
        Args:
            decryption_key: 32-byte AES-256 key (same key used for encoding).
        """
        if len(decryption_key) != 32:
            raise ValueError("Decryption key must be exactly 32 bytes")
        self._key = decryption_key

    def decode(self, data: bytes) -> Soul:
        """
        Decode encrypted bytes back into a Soul.

        Args:
            data: Encrypted payload from SoulEncoder.encode()

        Returns:
            Reconstructed Soul object.

        Raises:
            SoulDecodeError: On invalid format, wrong key, or corrupted data.
        """
        if len(data) < 22:  # 5 + 1 + 12 + 4 minimum
            raise SoulDecodeError("Payload too short")

        # Parse header
        magic = data[:5]
        if magic != SoulEncoder.MAGIC:
            raise SoulDecodeError(f"Invalid magic bytes: {magic!r}")

        version = data[5]
        if version != SoulEncoder.FORMAT_VERSION:
            raise SoulDecodeError(f"Unsupported format version: {version}")

        nonce = data[6:18]
        original_size = int.from_bytes(data[18:22], "big")
        ciphertext = data[22:]

        # Decrypt
        try:
            aesgcm = AESGCM(self._key)
            compressed = aesgcm.decrypt(nonce, ciphertext, associated_data=SoulEncoder.MAGIC)
        except Exception as e:
            raise SoulDecodeError(f"Decryption failed (wrong key or corrupted data): {e}") from e

        # Decompress
        try:
            raw = zlib.decompress(compressed)
        except zlib.error as e:
            raise SoulDecodeError(f"Decompression failed: {e}") from e

        if len(raw) != original_size:
            raise SoulDecodeError(
                f"Size mismatch: expected {original_size}, got {len(raw)}"
            )

        # Deserialize
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SoulDecodeError(f"JSON parse failed: {e}") from e

        return self._reconstruct(obj)

    def decode_hex(self, hex_string: str) -> Soul:
        """Decode from hex string."""
        return self.decode(bytes.fromhex(hex_string))

    @staticmethod
    def _reconstruct(obj: dict) -> Soul:
        """Reconstruct Soul from deserialized dict."""
        fragments = [
            SoulFragment(**frag) for frag in obj.pop("fragments", [])
        ]
        soul = Soul(
            agent_id=obj["agent_id"],
            version=obj.get("version", 1),
            fragments=fragments,
            created_at=obj.get("created_at", 0),
            model_origin=obj.get("model_origin", ""),
            metadata=obj.get("metadata", {}),
        )
        return soul
