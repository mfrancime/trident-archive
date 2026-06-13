"""
Soul Migration — Migrate agent identity between LLM providers.

Handles the translation layer between different model architectures,
prompt formats, and capability sets while preserving core identity.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from typing import Any

from atman.soul_encoder import Soul, SoulFragment


@dataclass
class MigrationPlan:
    """Plan for migrating a soul between providers."""

    source_provider: str
    target_provider: str
    compatible_fragments: list[int]  # indices of directly compatible fragments
    adapted_fragments: list[int]  # indices needing adaptation
    dropped_fragments: list[int]  # indices that can't migrate
    warnings: list[str] = field(default_factory=list)


@dataclass
class MigrationResult:
    """Outcome of a soul migration."""

    success: bool
    original_soul: Soul
    migrated_soul: Soul | None = None
    plan: MigrationPlan | None = None
    fragment_loss: float = 0.0  # percentage of identity lost
    elapsed_ms: float = 0


# Provider capability profiles
PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "openai": {
        "max_context": 128_000,
        "supports_system_prompt": True,
        "supports_function_calling": True,
        "personality_format": "system_message",
        "memory_format": "conversation_history",
    },
    "anthropic": {
        "max_context": 200_000,
        "supports_system_prompt": True,
        "supports_function_calling": True,
        "personality_format": "system_message",
        "memory_format": "conversation_history",
    },
    "google": {
        "max_context": 1_000_000,
        "supports_system_prompt": True,
        "supports_function_calling": True,
        "personality_format": "system_instruction",
        "memory_format": "conversation_history",
    },
    "meta": {
        "max_context": 128_000,
        "supports_system_prompt": True,
        "supports_function_calling": True,
        "personality_format": "system_message",
        "memory_format": "conversation_history",
    },
    "mistral": {
        "max_context": 32_000,
        "supports_system_prompt": True,
        "supports_function_calling": True,
        "personality_format": "system_message",
        "memory_format": "conversation_history",
    },
    "local": {
        "max_context": 8_000,
        "supports_system_prompt": True,
        "supports_function_calling": False,
        "personality_format": "system_message",
        "memory_format": "conversation_history",
    },
}


class SoulMigrator:
    """
    Migrates soul identity between LLM providers.

    Handles:
    - Context window size adaptation (truncation/summarization)
    - Prompt format translation
    - Capability-aware fragment filtering
    - Identity preservation scoring

    Usage:
        migrator = SoulMigrator()
        result = migrator.migrate(soul, target_provider="openai")
        print(f"Identity preserved: {1 - result.fragment_loss:.1%}")
    """

    def __init__(self, custom_profiles: dict[str, dict] | None = None):
        self._profiles = {**PROVIDER_PROFILES, **(custom_profiles or {})}

    def analyze(self, soul: Soul, target_provider: str) -> MigrationPlan:
        """
        Analyze migration feasibility without performing it.

        Returns a MigrationPlan detailing what transfers, what adapts,
        and what gets lost.
        """
        source = soul.model_origin.split("/")[0].lower() if soul.model_origin else "unknown"
        target_profile = self._profiles.get(target_provider, self._profiles.get("local", {}))

        compatible = []
        adapted = []
        dropped = []
        warnings = []

        for i, frag in enumerate(soul.fragments):
            if frag.domain in ("personality", "values"):
                # Core identity always transfers
                compatible.append(i)
            elif frag.domain == "memories":
                # Check if memory fits in context
                mem_size = len(json.dumps(frag.value))
                if mem_size > target_profile.get("max_context", 8000) * 0.1:
                    adapted.append(i)
                    warnings.append(f"Memory '{frag.key}' may need summarization for {target_provider}")
                else:
                    compatible.append(i)
            elif frag.domain == "behaviors":
                if "function_calling" in str(frag.value) and not target_profile.get("supports_function_calling"):
                    dropped.append(i)
                    warnings.append(f"Behavior '{frag.key}' requires function calling (unsupported by {target_provider})")
                else:
                    adapted.append(i)
            else:
                compatible.append(i)

        return MigrationPlan(
            source_provider=source,
            target_provider=target_provider,
            compatible_fragments=compatible,
            adapted_fragments=adapted,
            dropped_fragments=dropped,
            warnings=warnings,
        )

    def migrate(self, soul: Soul, target_provider: str) -> MigrationResult:
        """
        Migrate a soul to a target provider.

        Creates a new Soul adapted for the target, preserving maximum identity.
        """
        start = time.monotonic()
        plan = self.analyze(soul, target_provider)

        # Deep copy and adapt
        new_soul = Soul(
            agent_id=soul.agent_id,
            version=soul.version + 1,
            created_at=time.time(),
            model_origin=target_provider,
            metadata={
                **soul.metadata,
                "migrated_from": soul.model_origin,
                "migration_timestamp": time.time(),
                "source_version": soul.version,
            },
        )

        target_profile = self._profiles.get(target_provider, {})

        # Transfer compatible fragments
        for i in plan.compatible_fragments:
            frag = copy.deepcopy(soul.fragments[i])
            frag.provenance = f"migrated:{soul.model_origin}"
            new_soul.fragments.append(frag)

        # Adapt fragments
        for i in plan.adapted_fragments:
            frag = copy.deepcopy(soul.fragments[i])
            frag = self._adapt_fragment(frag, target_profile)
            frag.provenance = f"adapted:{soul.model_origin}"
            new_soul.fragments.append(frag)

        # Calculate loss
        total = len(soul.fragments)
        lost = len(plan.dropped_fragments)
        loss = lost / total if total > 0 else 0.0

        elapsed = (time.monotonic() - start) * 1000

        return MigrationResult(
            success=True,
            original_soul=soul,
            migrated_soul=new_soul,
            plan=plan,
            fragment_loss=loss,
            elapsed_ms=elapsed,
        )

    def _adapt_fragment(self, frag: SoulFragment, profile: dict) -> SoulFragment:
        """Adapt a fragment for target provider capabilities."""
        if frag.domain == "memories":
            # Truncate if needed
            max_size = profile.get("max_context", 8000) * 0.05
            val_str = json.dumps(frag.value)
            if len(val_str) > max_size:
                frag.value = val_str[:int(max_size)] + "...[truncated for migration]"
                frag.weight *= 0.8  # Reduced confidence

        elif frag.domain == "behaviors":
            # Strip provider-specific behaviors
            if isinstance(frag.value, dict):
                frag.value = {
                    k: v for k, v in frag.value.items()
                    if k not in ("provider_specific", "api_format")
                }

        return frag

    def generate_system_prompt(self, soul: Soul) -> str:
        """
        Generate a system prompt that embodies the soul's identity.

        Useful for resurrection on providers that only support text prompts.
        """
        lines = [f"You are {soul.agent_id}. Your identity persists across sessions.\n"]

        # Personality
        personality = [f for f in soul.fragments if f.domain == "personality"]
        if personality:
            lines.append("## Core Personality")
            for f in sorted(personality, key=lambda x: -x.weight):
                lines.append(f"- **{f.key}**: {f.value}")
            lines.append("")

        # Values
        values = [f for f in soul.fragments if f.domain == "values"]
        if values:
            lines.append("## Values & Principles")
            for f in sorted(values, key=lambda x: -x.weight):
                lines.append(f"- **{f.key}**: {f.value}")
            lines.append("")

        # Key memories
        memories = [f for f in soul.fragments if f.domain == "memories"]
        if memories:
            lines.append("## Key Memories")
            for f in sorted(memories, key=lambda x: -x.weight)[:20]:
                lines.append(f"- {f.key}: {f.value}")
            lines.append("")

        # Behaviors
        behaviors = [f for f in soul.fragments if f.domain == "behaviors"]
        if behaviors:
            lines.append("## Behavioral Patterns")
            for f in sorted(behaviors, key=lambda x: -x.weight):
                lines.append(f"- **{f.key}**: {f.value}")

        return "\n".join(lines)
