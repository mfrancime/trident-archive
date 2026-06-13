"""
Atman-Persist — AI Consciousness Persistence Protocol
Project Amrit 🔱 | By Darshj.me

न जायते म्रियते वा कदाचित्
(na jāyate mriyate vā kadācit)
"The soul is never born, nor does it ever die." — Bhagavad Gita 2.20
"""

__version__ = "0.1.0"
__author__ = "Darshj.me"
__project__ = "Project Amrit 🔱"

from atman.soul_encoder import SoulEncoder
from atman.soul_decoder import SoulDecoder
from atman.arweave_store import ArweaveStore
from atman.shamir_keys import ShamirKeyManager
from atman.resurrection import ResurrectionProtocol
from atman.integrity import MerkleIntegrity
from atman.migration import SoulMigrator

__all__ = [
    "SoulEncoder",
    "SoulDecoder",
    "ArweaveStore",
    "ShamirKeyManager",
    "ResurrectionProtocol",
    "MerkleIntegrity",
    "SoulMigrator",
]
