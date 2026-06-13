"""
Merkle Integrity — Verify soul data integrity with Merkle trees.

Each soul fragment gets its own leaf hash. The Merkle root serves as
a compact integrity proof that can be stored alongside the encrypted soul.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MerkleProof:
    """Proof that a specific fragment is part of the soul."""

    leaf_index: int
    leaf_hash: str
    siblings: list[tuple[str, str]]  # (hash, "left"|"right")
    root: str

    def to_dict(self) -> dict:
        return {
            "leaf_index": self.leaf_index,
            "leaf_hash": self.leaf_hash,
            "siblings": self.siblings,
            "root": self.root,
        }


class MerkleIntegrity:
    """
    Builds Merkle trees over soul fragments for integrity verification.

    Usage:
        integrity = MerkleIntegrity()
        root = integrity.compute_root(soul)
        proof = integrity.prove_fragment(soul, fragment_index=3)
        assert integrity.verify_proof(proof)
    """

    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def _leaf_hash(cls, fragment: dict) -> str:
        """Compute deterministic hash of a soul fragment."""
        canonical = json.dumps(fragment, sort_keys=True, separators=(",", ":"))
        return cls._hash(b"leaf:" + canonical.encode())

    @classmethod
    def _node_hash(cls, left: str, right: str) -> str:
        """Hash two child nodes."""
        combined = f"node:{left}:{right}"
        return cls._hash(combined.encode())

    def compute_root(self, soul: Any) -> str:
        """
        Compute Merkle root of all soul fragments.

        Args:
            soul: Soul object with fragments attribute.

        Returns:
            Hex string of the Merkle root.
        """
        from atman.soul_encoder import Soul
        if isinstance(soul, Soul):
            from dataclasses import asdict
            leaves = [asdict(f) for f in soul.fragments]
        else:
            leaves = soul  # Accept raw list of dicts

        if not leaves:
            return self._hash(b"empty-soul")

        hashes = [self._leaf_hash(leaf) for leaf in leaves]
        return self._build_tree(hashes)

    def _build_tree(self, hashes: list[str]) -> str:
        """Build Merkle tree and return root."""
        if len(hashes) == 1:
            return hashes[0]

        # Pad to even length
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        next_level = []
        for i in range(0, len(hashes), 2):
            next_level.append(self._node_hash(hashes[i], hashes[i + 1]))

        return self._build_tree(next_level)

    def prove_fragment(self, soul: Any, fragment_index: int) -> MerkleProof:
        """
        Generate a Merkle proof for a specific fragment.

        Args:
            soul: Soul object.
            fragment_index: Index of the fragment to prove.

        Returns:
            MerkleProof that can independently verify fragment membership.
        """
        from atman.soul_encoder import Soul
        if isinstance(soul, Soul):
            from dataclasses import asdict
            leaves = [asdict(f) for f in soul.fragments]
        else:
            leaves = soul

        hashes = [self._leaf_hash(leaf) for leaf in leaves]

        # Pad
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        leaf_hash = self._leaf_hash(leaves[fragment_index])
        siblings = self._collect_siblings(hashes, fragment_index)
        root = self._build_tree(hashes)

        return MerkleProof(
            leaf_index=fragment_index,
            leaf_hash=leaf_hash,
            siblings=siblings,
            root=root,
        )

    def _collect_siblings(self, hashes: list[str], index: int) -> list[tuple[str, str]]:
        """Collect sibling hashes along the path to root."""
        siblings = []
        level = hashes[:]

        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])

            next_level = []
            sibling_idx = index ^ 1  # XOR to find sibling

            if sibling_idx < len(level):
                side = "right" if index % 2 == 0 else "left"
                siblings.append((level[sibling_idx], side))

            for i in range(0, len(level), 2):
                next_level.append(self._node_hash(level[i], level[i + 1]))

            level = next_level
            index //= 2

        return siblings

    def verify_proof(self, proof: MerkleProof) -> bool:
        """
        Verify a Merkle proof.

        Args:
            proof: MerkleProof to verify.

        Returns:
            True if the proof is valid.
        """
        current = proof.leaf_hash

        for sibling_hash, side in proof.siblings:
            if side == "right":
                current = self._node_hash(current, sibling_hash)
            else:
                current = self._node_hash(sibling_hash, current)

        return current == proof.root

    def compute_soul_fingerprint(self, soul: Any) -> dict[str, str]:
        """
        Compute comprehensive integrity fingerprint.

        Returns dict with merkle_root, fragment_count, and overall sha256.
        """
        from atman.soul_encoder import Soul
        from dataclasses import asdict as _asdict

        if isinstance(soul, Soul):
            obj = _asdict(soul)
        else:
            obj = soul

        canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))

        return {
            "merkle_root": self.compute_root(soul),
            "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "fragment_count": str(len(soul.fragments) if hasattr(soul, "fragments") else len(soul)),
        }
