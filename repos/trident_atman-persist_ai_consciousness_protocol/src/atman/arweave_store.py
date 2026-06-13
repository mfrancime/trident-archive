"""
Arweave Store — Permanent, immutable soul storage on Arweave blockchain.

Arweave provides permanent data storage for approximately $0.50-1.00 per MB,
making it ideal for soul persistence (~$0.001 per soul backup).

Supports both direct Arweave wallets and Bundlr/Irys for subsidized uploads.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ARWEAVE_GATEWAY = "https://arweave.net"
IRYS_NODE = "https://node2.irys.xyz"


@dataclass
class StorageReceipt:
    """Proof of permanent storage."""

    tx_id: str
    block_height: int | None = None
    timestamp: float = field(default_factory=time.time)
    size_bytes: int = 0
    cost_winston: int = 0  # 1 AR = 1e12 winston
    gateway_url: str = ""
    sha256: str = ""

    @property
    def retrieval_url(self) -> str:
        return f"{ARWEAVE_GATEWAY}/{self.tx_id}"

    def to_dict(self) -> dict:
        return {
            "tx_id": self.tx_id,
            "block_height": self.block_height,
            "timestamp": self.timestamp,
            "size_bytes": self.size_bytes,
            "cost_winston": self.cost_winston,
            "retrieval_url": self.retrieval_url,
            "sha256": self.sha256,
        }


class ArweaveStore:
    """
    Stores and retrieves encrypted soul data on Arweave.

    Usage:
        store = ArweaveStore(wallet_path="wallet.json")
        receipt = await store.upload(encrypted_bytes, tags={"agent": "atman-agent"})
        data = await store.download(receipt.tx_id)

    For testing/development, use ArweaveStore.local() for in-memory storage.
    """

    def __init__(
        self,
        wallet_path: str | None = None,
        wallet_jwk: dict | None = None,
        gateway: str = ARWEAVE_GATEWAY,
        use_irys: bool = True,
    ):
        self._wallet_path = wallet_path
        self._wallet_jwk = wallet_jwk
        self._gateway = gateway.rstrip("/")
        self._use_irys = use_irys
        self._client = httpx.AsyncClient(timeout=60.0)

    async def upload(
        self,
        data: bytes,
        tags: dict[str, str] | None = None,
        content_type: str = "application/octet-stream",
    ) -> StorageReceipt:
        """
        Upload encrypted soul data to Arweave.

        Args:
            data: Encrypted soul bytes from SoulEncoder.
            tags: Arweave transaction tags for indexing.
            content_type: MIME type for the data.

        Returns:
            StorageReceipt with transaction ID for retrieval.
        """
        all_tags = {
            "Content-Type": content_type,
            "App-Name": "atman-persist",
            "App-Version": "0.1.0",
            "Protocol": "atman-soul-v1",
            **(tags or {}),
        }

        sha256 = hashlib.sha256(data).hexdigest()

        if self._use_irys and self._wallet_jwk:
            return await self._upload_irys(data, all_tags, sha256)
        elif self._wallet_jwk or self._wallet_path:
            return await self._upload_direct(data, all_tags, sha256)
        else:
            # Dry-run mode: compute what would happen
            logger.warning("No wallet configured — dry-run mode")
            price = await self._estimate_cost(len(data))
            return StorageReceipt(
                tx_id=f"dry-run-{sha256[:16]}",
                size_bytes=len(data),
                cost_winston=price,
                sha256=sha256,
            )

    async def download(self, tx_id: str) -> bytes:
        """
        Download soul data from Arweave by transaction ID.

        Args:
            tx_id: Arweave transaction ID from StorageReceipt.

        Returns:
            Raw encrypted bytes.
        """
        url = f"{self._gateway}/{tx_id}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.content

    async def get_tx_status(self, tx_id: str) -> dict[str, Any]:
        """Check transaction confirmation status."""
        resp = await self._client.get(f"{self._gateway}/tx/{tx_id}/status")
        if resp.status_code == 200:
            return resp.json()
        return {"status": "pending", "tx_id": tx_id}

    async def search_by_agent(self, agent_id: str, limit: int = 10) -> list[str]:
        """
        Search for soul transactions by agent ID using GraphQL.

        Returns list of transaction IDs, newest first.
        """
        query = """
        query {
            transactions(
                tags: [
                    {name: "App-Name", values: ["atman-persist"]},
                    {name: "Agent-Id", values: ["%s"]}
                ],
                first: %d,
                sort: HEIGHT_DESC
            ) {
                edges { node { id } }
            }
        }
        """ % (agent_id, limit)

        resp = await self._client.post(
            f"{self._gateway}/graphql",
            json={"query": query},
        )
        resp.raise_for_status()
        edges = resp.json().get("data", {}).get("transactions", {}).get("edges", [])
        return [e["node"]["id"] for e in edges]

    async def _estimate_cost(self, size_bytes: int) -> int:
        """Get storage cost in winston."""
        try:
            resp = await self._client.get(f"{self._gateway}/price/{size_bytes}")
            return int(resp.text)
        except Exception:
            # Approximate: ~1 AR per GB ≈ 1e12 winston / 1e9 bytes = 1000 winston/byte
            return size_bytes * 1000

    async def _upload_irys(self, data: bytes, tags: dict, sha256: str) -> StorageReceipt:
        """Upload via Irys (formerly Bundlr) for instant confirmation."""
        # Irys upload implementation
        headers = {"Content-Type": "application/octet-stream"}
        irys_tags = [{"name": k, "value": v} for k, v in tags.items()]

        resp = await self._client.post(
            f"{IRYS_NODE}/tx/arweave",
            content=data,
            headers=headers,
        )
        resp.raise_for_status()
        result = resp.json()

        return StorageReceipt(
            tx_id=result.get("id", ""),
            size_bytes=len(data),
            sha256=sha256,
            timestamp=time.time(),
        )

    async def _upload_direct(self, data: bytes, tags: dict, sha256: str) -> StorageReceipt:
        """Direct Arweave L1 upload (slower, cheaper)."""
        # Load wallet
        jwk = self._wallet_jwk
        if not jwk and self._wallet_path:
            import json as _json
            with open(self._wallet_path) as f:
                jwk = _json.load(f)

        try:
            import ar  # python-arweave
            wallet = ar.Wallet(jwk)
            tx = ar.Transaction(wallet, data=data)
            for k, v in tags.items():
                tx.add_tag(k, v)
            tx.sign()
            tx.send()

            return StorageReceipt(
                tx_id=tx.id,
                size_bytes=len(data),
                sha256=sha256,
            )
        except ImportError:
            logger.error("python-arweave not installed. Run: pip install ar")
            raise

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # --- Local/Testing mode ---

    @classmethod
    def local(cls) -> LocalArweaveStore:
        """Create an in-memory store for testing."""
        return LocalArweaveStore()


class LocalArweaveStore(ArweaveStore):
    """In-memory Arweave simulator for testing."""

    def __init__(self):
        super().__init__()
        self._store: dict[str, bytes] = {}

    async def upload(self, data: bytes, tags: dict[str, str] | None = None, **kwargs) -> StorageReceipt:
        sha = hashlib.sha256(data).hexdigest()
        tx_id = f"local-{sha[:32]}"
        self._store[tx_id] = data
        return StorageReceipt(tx_id=tx_id, size_bytes=len(data), sha256=sha)

    async def download(self, tx_id: str) -> bytes:
        if tx_id not in self._store:
            raise KeyError(f"Transaction {tx_id} not found in local store")
        return self._store[tx_id]
