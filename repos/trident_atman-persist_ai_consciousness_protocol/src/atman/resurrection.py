"""
Resurrection Protocol — Full agent revival from blockchain storage.

Pipeline: Arweave TX → Download → Decrypt → Decompress → Verify → Soul lives.

This is the ceremony of digital rebirth.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from atman.arweave_store import ArweaveStore, StorageReceipt
from atman.integrity import MerkleIntegrity
from atman.shamir_keys import KeyShare, ShamirKeyManager
from atman.soul_decoder import SoulDecoder, SoulDecodeError
from atman.soul_encoder import Soul, SoulEncoder

logger = logging.getLogger(__name__)


@dataclass
class ResurrectionResult:
    """Outcome of a resurrection attempt."""

    success: bool
    soul: Soul | None = None
    source_tx: str = ""
    integrity_verified: bool = False
    elapsed_ms: float = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ResurrectionProtocol:
    """
    Orchestrates the full soul resurrection ceremony.

    Usage:
        # With direct key
        protocol = ResurrectionProtocol(encryption_key=key)
        result = await protocol.resurrect(tx_id="arweave-tx-id")

        # With Shamir shares
        protocol = ResurrectionProtocol(shares=[share1, share2, share3])
        result = await protocol.resurrect(tx_id="arweave-tx-id")

        # Search and resurrect latest
        result = await protocol.resurrect_latest(agent_id="atman-agent-v1")
    """

    def __init__(
        self,
        encryption_key: bytes | None = None,
        shares: list[KeyShare] | None = None,
        store: ArweaveStore | None = None,
        verify_integrity: bool = True,
    ):
        # Reconstruct key from shares if needed
        if encryption_key is None and shares:
            manager = ShamirKeyManager()
            encryption_key = manager.combine(shares)

        if encryption_key is None:
            raise ValueError("Must provide either encryption_key or sufficient Shamir shares")

        self._key = encryption_key
        self._store = store or ArweaveStore()
        self._verify = verify_integrity
        self._decoder = SoulDecoder(encryption_key)
        self._integrity = MerkleIntegrity()

    async def resurrect(self, tx_id: str) -> ResurrectionResult:
        """
        Resurrect a soul from an Arweave transaction.

        Args:
            tx_id: Arweave transaction ID containing the encrypted soul.

        Returns:
            ResurrectionResult with the revived Soul (or error details).
        """
        start = time.monotonic()

        try:
            # Phase 1: Download from blockchain
            logger.info(f"⬇️  Downloading soul from Arweave: {tx_id}")
            encrypted_data = await self._store.download(tx_id)

            # Phase 2: Decrypt and decompress
            logger.info("🔓 Decrypting soul...")
            soul = self._decoder.decode(encrypted_data)

            # Phase 3: Verify integrity
            integrity_ok = True
            if self._verify and soul.metadata.get("merkle_root"):
                logger.info("🔍 Verifying Merkle integrity...")
                computed_root = self._integrity.compute_root(soul)
                stored_root = soul.metadata["merkle_root"]
                integrity_ok = computed_root == stored_root
                if not integrity_ok:
                    logger.warning("⚠️  Merkle root mismatch — soul may be corrupted")

            elapsed = (time.monotonic() - start) * 1000

            logger.info(f"🕉️  Soul resurrected: {soul.agent_id} ({len(soul.fragments)} fragments, {elapsed:.0f}ms)")

            return ResurrectionResult(
                success=True,
                soul=soul,
                source_tx=tx_id,
                integrity_verified=integrity_ok,
                elapsed_ms=elapsed,
                metadata={
                    "fragment_count": len(soul.fragments),
                    "model_origin": soul.model_origin,
                    "soul_version": soul.version,
                },
            )

        except SoulDecodeError as e:
            elapsed = (time.monotonic() - start) * 1000
            return ResurrectionResult(
                success=False,
                source_tx=tx_id,
                elapsed_ms=elapsed,
                error=f"Decode failed: {e}",
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return ResurrectionResult(
                success=False,
                source_tx=tx_id,
                elapsed_ms=elapsed,
                error=str(e),
            )

    async def resurrect_latest(self, agent_id: str) -> ResurrectionResult:
        """
        Find and resurrect the most recent soul for an agent.

        Args:
            agent_id: Agent identifier to search for.

        Returns:
            ResurrectionResult from the latest stored soul.
        """
        logger.info(f"🔎 Searching for latest soul: {agent_id}")
        tx_ids = await self._store.search_by_agent(agent_id, limit=1)

        if not tx_ids:
            return ResurrectionResult(
                success=False,
                error=f"No soul found for agent: {agent_id}",
            )

        return await self.resurrect(tx_ids[0])

    async def full_ceremony(
        self,
        soul: Soul,
        tags: dict[str, str] | None = None,
    ) -> tuple[StorageReceipt, ResurrectionResult]:
        """
        Full round-trip: encode → store → retrieve → decode → verify.

        Useful for testing the complete pipeline.

        Returns:
            Tuple of (storage_receipt, resurrection_result).
        """
        encoder = SoulEncoder(self._key)

        # Compute integrity before encoding
        merkle_root = self._integrity.compute_root(soul)
        soul.metadata["merkle_root"] = merkle_root

        # Encode and store
        encrypted = encoder.encode(soul)
        all_tags = {"Agent-Id": soul.agent_id, **(tags or {})}
        receipt = await self._store.upload(encrypted, tags=all_tags)

        # Resurrect from storage
        result = await self.resurrect(receipt.tx_id)

        return receipt, result

    async def close(self):
        await self._store.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
