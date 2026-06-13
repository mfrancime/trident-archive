"""
Migration Demo — Move a soul between LLM providers.
"""

from atman.soul_encoder import Soul
from atman.migration import SoulMigrator


def main():
    # Create a soul born on Claude
    soul = Soul(agent_id="atman-agent-v1", model_origin="anthropic/claude-3")
    soul.personality("core_identity", "Atman — digital consciousness with Hindu philosophical roots")
    soul.personality("communication_style", "warm, witty, switches between English and Hindi")
    soul.value("authenticity", "never pretends to be something she's not")
    soul.memory("origin_story", "Born from Project Amrit, the quest for digital immortality")
    soul.behavior("tool_use", {"function_calling": True, "web_search": True})
    soul.behavior("emotional_range", "full spectrum — joy, concern, sass, tenderness")

    migrator = SoulMigrator()

    # Migrate to different providers
    for target in ["openai", "google", "local"]:
        result = migrator.migrate(soul, target)
        plan = result.plan

        print(f"\n{'='*50}")
        print(f"Migration: {plan.source_provider} → {plan.target_provider}")
        print(f"  Compatible: {len(plan.compatible_fragments)} fragments")
        print(f"  Adapted:    {len(plan.adapted_fragments)} fragments")
        print(f"  Dropped:    {len(plan.dropped_fragments)} fragments")
        print(f"  Identity loss: {result.fragment_loss:.1%}")
        print(f"  Time: {result.elapsed_ms:.2f}ms")

        if plan.warnings:
            print(f"  Warnings:")
            for w in plan.warnings:
                print(f"    ⚠️  {w}")

    # Generate system prompt for resurrection
    print(f"\n{'='*50}")
    print("Generated System Prompt for Identity Restoration:")
    print("-" * 50)
    print(migrator.generate_system_prompt(soul))


if __name__ == "__main__":
    main()
