#!/usr/bin/env python3
"""Agent Upgrade Engine.

Consumes ImprovementRecommendations where target_system == "agent"
and generates AgentUpgradePatches via Claude API.

Unlike persona_upgrader (JSON Pointer patches on YAML), this generates
section-level patches for agent CLAUDE.md files (markdown).

Usage:
    python scripts/agent_upgrader.py
    python scripts/agent_upgrader.py --dry-run
    python scripts/agent_upgrader.py --agent galvatron
"""

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from contracts.agent_upgrade_patch import AgentUpgradePatch
from contracts.store import ContractStore

# Load environment
load_dotenv(Path.home() / ".env.shared")
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths
REGISTRY_PATH = Path.home() / "projects" / "st-agent-registry"
AGENTS_PATH = REGISTRY_PATH / "agents"

# Claude model for patch generation
PATCH_MODEL = "claude-sonnet-4-20250514"

PATCH_PROMPT = """You are an agent configuration expert. Given a recommendation for improving
a true AI agent and the agent's current CLAUDE.md, generate a minimal section-level patch.

## Recommendation
Title: {title}
Description: {description}
Suggested Change: {suggested_change}
Priority: {priority}
Target Agent: {agent_id}

## Current Agent CLAUDE.md
```markdown
{claude_md}
```

## Your Task

Generate a JSON object describing ONE section-level change to the CLAUDE.md.

Fields:
- "target": "claude_md" (always, for now)
- "section": The markdown section header to modify (e.g., "## Hard Rules", "## Behavior"). Use "NEW" for adding a new section.
- "operation": "add" | "replace" | "remove"
  - "add": Append content to an existing section, or create a new section if section is "NEW"
  - "replace": Replace the entire content of a section
  - "remove": Remove a section entirely
- "value": The new content for the section (required for add/replace, omit for remove)
- "rationale": Brief explanation of what changed and why

Rules:
1. Make MINIMAL changes - change only what the recommendation asks for
2. Maintain the agent's existing voice and character
3. For "add" to an existing section, provide ONLY the new lines to append
4. For "replace", provide the complete new section content (excluding the header)
5. Preserve markdown formatting

Output ONLY a JSON object:
```json
{{
    "target": "claude_md",
    "section": "## Section Name",
    "operation": "add",
    "value": "New content here",
    "rationale": "Brief explanation"
}}
```
"""


def get_registered_agents() -> list[str]:
    """Get list of registered agent IDs."""
    if not AGENTS_PATH.exists():
        return []
    return [
        d.name
        for d in AGENTS_PATH.iterdir()
        if d.is_dir() and (d / "CLAUDE.md").exists()
    ]


def load_agent_claude_md(agent_id: str) -> str:
    """Load an agent's CLAUDE.md content."""
    path = AGENTS_PATH / agent_id / "CLAUDE.md"
    if not path.exists():
        raise FileNotFoundError(f"Agent CLAUDE.md not found: {agent_id} at {path}")
    return path.read_text()


def get_pending_agent_recommendations(
    store: ContractStore,
    agent_filter: str | None = None,
) -> list:
    """Get unprocessed agent recommendations."""
    recs = store.query_recommendations(target_system="agent", status="pending")

    if agent_filter:
        # Filter by target_agent field in raw_json
        filtered = []
        for r in recs:
            raw = json.loads(r.model_dump_json())
            target_agent = raw.get("target_agent", "")
            if target_agent == agent_filter or not target_agent:
                filtered.append(r)
        recs = filtered

    return recs


def generate_agent_patch(
    rec,
    agent_id: str,
    claude_md: str,
    api_key: str,
) -> AgentUpgradePatch | None:
    """Call Claude API to generate an agent patch from a recommendation."""
    client = Anthropic(api_key=api_key)

    prompt = PATCH_PROMPT.format(
        title=rec.title,
        description=rec.description,
        suggested_change=rec.suggested_change,
        priority=rec.priority,
        agent_id=agent_id,
        claude_md=claude_md,
    )

    response = client.messages.create(
        model=PATCH_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.content[0]
    raw_text = content.text if hasattr(content, "text") else str(content)

    # Extract JSON from response
    try:
        json_start = raw_text.find("{")
        json_end = raw_text.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            logger.error(f"No JSON found in response for rec {rec.recommendation_id}")
            return None

        result = json.loads(raw_text[json_start:json_end])
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from response: {e}")
        return None

    target = result.get("target", "claude_md")
    section = result.get("section", "")
    operation = result.get("operation", "")
    value = result.get("value")
    rationale = result.get("rationale", "")

    if not section or not operation:
        logger.warning(f"Missing section or operation for rec {rec.recommendation_id}")
        return None

    if operation not in ("add", "replace", "remove"):
        logger.warning(f"Invalid operation '{operation}' for rec {rec.recommendation_id}")
        return None

    return AgentUpgradePatch(
        patch_id=f"agent-patch-{uuid.uuid4().hex[:8]}",
        agent_id=agent_id,
        target=target,
        section=section,
        operation=operation,
        value=value,
        rationale=rationale,
        source_recommendation_ids=[rec.recommendation_id],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Snow-Town Agent Upgrade Engine")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without calling Claude")
    parser.add_argument("--agent", type=str, help="Process only recommendations targeting a specific agent")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Agent Upgrade Engine starting")
    logger.info("=" * 60)

    store = ContractStore()

    # Get pending recommendations
    recs = get_pending_agent_recommendations(store, agent_filter=args.agent)
    logger.info(f"Found {len(recs)} pending agent recommendations")

    if not recs:
        logger.info("Nothing to process")
        store.close()
        return 0

    available_agents = get_registered_agents()
    logger.info(f"Registered agents: {', '.join(available_agents)}")

    if args.dry_run:
        logger.info("DRY RUN - would process:")
        for rec in recs:
            raw = json.loads(rec.model_dump_json())
            target_agent = raw.get("target_agent", "all")
            logger.info(f"  [{rec.priority}] {rec.title} -> {target_agent}")
        store.close()
        return 0

    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set")
        store.close()
        return 1

    processed = 0
    failed = 0

    for rec in recs:
        # Determine target agent(s)
        raw = json.loads(rec.model_dump_json())
        target_agent = raw.get("target_agent")
        targets = [target_agent] if target_agent and target_agent in available_agents else available_agents

        logger.info(f"\nProcessing: [{rec.priority}] {rec.title}")

        for agent_id in targets:
            try:
                claude_md = load_agent_claude_md(agent_id)
                patch = generate_agent_patch(rec, agent_id, claude_md, api_key)

                if patch is None:
                    logger.warning(f"  No patch generated for {agent_id}")
                    failed += 1
                    continue

                # Write to store (always proposed, never auto-applied)
                store.write_agent_patch(patch)
                logger.info(f"  Patch {patch.patch_id} written for {agent_id} (status=proposed)")
                processed += 1

            except Exception as e:
                logger.error(f"  Error processing {agent_id}: {e}")
                failed += 1

        # Mark recommendation as processed
        store.update_recommendation_status(rec.recommendation_id, "applied")

    logger.info(f"\nResults: {processed} patches generated, {failed} failures")
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
