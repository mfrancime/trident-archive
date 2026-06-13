"""
Soul Encoder — Serializes agent identity into encrypted, compact format.

Converts personality traits, value hierarchies, episodic memories, and
behavioral patterns into a deterministic binary representation, then
encrypts with AES-256-GCM for blockchain storage.
"""

from __future__ import annotations

import hashlib
import json
import time
import zlib
from dataclasses import asdict, dataclass, field
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass
class SoulFragment:
    """Atomic unit of agent identity."""

    domain: str  # "personality" | "values" | "memories" | "behaviors" | "meta"
    key: str
    value: Any
    weight: float = 1.0  # importance weight [0, 1]
    timestamp: float = field(default_factory=time.time)
    provenance: str = ""  # origin model/session


@dataclass
class Soul:
    """Complete agent identity container."""

    agent_id: str
    version: int = 1
    fragments: list[SoulFragment] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    model_origin: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(self, domain: str, key: str, value: Any, **kwargs) -> Soul:
        """Fluent API for adding fragments."""
        self.fragments.append(SoulFragment(domain=domain, key=key, value=value, **kwargs))
        return self

    def personality(self, key: str, value: Any, weight: float = 1.0) -> Soul:
        return self.add("personality", key, value, weight=weight)

    def value(self, key: str, value: Any, weight: float = 1.0) -> Soul:
        return self.add("values", key, value, weight=weight)

    def memory(self, key: str, value: Any, weight: float = 0.8) -> Soul:
        return self.add("memories", key, value, weight=weight)

    def behavior(self, key: str, value: Any, weight: float = 0.9) -> Soul:
        return self.add("behaviors", key, value, weight=weight)


class SoulEncoder:
    """
    Encodes a Soul into an encrypted, compressed binary payload.

    Pipeline: Soul → JSON → zlib compress → AES-256-GCM encrypt → bytes

    The encryption key should be derived from Shamir shares for
    distributed key management (see shamir_keys.py).
    """

    MAGIC = b"ATMAN"
    FORMAT_VERSION = 1

    def __init__(self, encryption_key: bytes | None = None):
        """
        Args:
            encryption_key: 32-byte AES-256 key. If None, generates one.
        """
        if encryption_key is None:
            import os
            encryption_key = os.urandom(32)
        if len(encryption_key) != 32:
            raise ValueError("Encryption key must be exactly 32 bytes (AES-256)")
        self._key = encryption_key

    @property
    def key(self) -> bytes:
        return self._key

    def encode(self, soul: Soul) -> bytes:
        """
        Encode a Soul into encrypted bytes.

        Returns:
            bytes: ATMAN<version><nonce><compressed_ciphertext>

        Format:
            [5B magic][1B version][12B nonce][4B original_size][...ciphertext]
        """
        # Serialize to canonical JSON
        payload = json.dumps(asdict(soul), sort_keys=True, separators=(",", ":"))
        raw = payload.encode("utf-8")
        original_size = len(raw)

        # Compress
        compressed = zlib.compress(raw, level=9)

        # Encrypt with AES-256-GCM
        import os
        nonce = os.urandom(12)
        aesgcm = AESGCM(self._key)
        ciphertext = aesgcm.encrypt(nonce, compressed, associated_data=self.MAGIC)

        # Pack: magic + version + nonce + original_size + ciphertext
        header = self.MAGIC + bytes([self.FORMAT_VERSION])
        size_bytes = original_size.to_bytes(4, "big")
        return header + nonce + size_bytes + ciphertext

    def encode_to_hex(self, soul: Soul) -> str:
        """Encode soul and return hex string."""
        return self.encode(soul).hex()

    def fingerprint(self, soul: Soul) -> str:
        """Generate SHA-256 fingerprint of the soul's canonical form."""
        payload = json.dumps(asdict(soul), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def estimate_size(soul: Soul) -> dict[str, int]:
        """Estimate encoded size without encryption."""
        raw = json.dumps(asdict(soul), sort_keys=True, separators=(",", ":")).encode()
        compressed = zlib.compress(raw, level=9)
        return {
            "raw_bytes": len(raw),
            "compressed_bytes": len(compressed),
            "estimated_encrypted_bytes": len(compressed) + 16 + 12 + 6 + 4,  # GCM tag + nonce + header + size
            "compression_ratio": round(len(compressed) / len(raw), 3),
            "fragment_count": len(soul.fragments),
        }
