#!/usr/bin/env python3
"""Persona Upgrade Engine.

Consumes ImprovementRecommendations where target_system == "persona"
and generates PersonaUpgradePatches via Claude API.

Usage:
    python scripts/persona_upgrader.py
    python scripts/persona_upgrader.py --dry-run
    python scripts/persona_upgrader.py --auto-apply
    python scripts/persona_upgrader.py --persona christensen
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import yaml
from anthropic import Anthropic
from dotenv import load_dotenv

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from contracts.improvement_recommendation import ImprovementRecommendation
from contracts.persona_upgrade_patch import (
    PatchOperation,
    PersonaFieldPatch,
    PersonaUpgradePatch,
)
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
ACADEMY_PATH = Path.home() / "projects" / "st-agent-registry"
PERSONAS_PATH = ACADEMY_PATH / "personas"
SCHEMA_PATH = ACADEMY_PATH / "schema" / "persona-schema.json"

# Claude model for patch generation
PATCH_MODEL = "claude-sonnet-4-20250514"

PATCH_PROMPT = """You are a persona engineering expert. Given a recommendation for improving
an AI persona and the current persona YAML, generate a minimal set of changes.

## Recommendation
Title: {title}
Type: {recommendation_type}
Description: {description}
Suggested Change: {suggested_change}
Priority: {priority}

## Current Persona YAML
```yaml
{persona_yaml}
```

## Your Task

Generate a JSON array of patch operations. Each operation has:
- "operation": "add" | "replace" | "remove"
- "path": JSON Pointer path (e.g., "/voice/phrases/-" to append, "/voice/tone/0" to replace first item)
- "value": The new value (required for add/replace, omit for remove)

Rules:
1. Make MINIMAL changes - change only what the recommendation asks for
2. Maintain the persona's existing voice and character
3. Use JSON Pointer syntax for paths
4. For arrays, use "/-" to append
5. Ensure values match the YAML schema types

Output ONLY a JSON object with this structure:
```json
{{
    "patches": [...],
    "rationale": "Brief explanation of what changed and why"
}}
```
"""


def get_persona_ids() -> list[str]:
    """Get list of available persona IDs."""
    if not PERSONAS_PATH.exists():
        return []
    return [
        d.name
        for d in PERSONAS_PATH.iterdir()
        if d.is_dir() and (d / "persona.yaml").exists()
    ]


def load_persona_yaml(persona_id: str) -> str:
    """Load a persona's YAML content."""
    path = PERSONAS_PATH / persona_id / "persona.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Persona not found: {persona_id} at {path}")
    return path.read_text()


def get_pending_recommendations(
    store: ContractStore,
    persona_filter: str | None = None,
) -> list[ImprovementRecommendation]:
    """Get unprocessed persona recommendations."""
    recs = store.query_recommendations(target_system="persona", status="pending")

    if persona_filter:
        recs = [r for r in recs if persona_filter in r.target_persona_ids or not r.target_persona_ids]

    return recs


def generate_patch(
    rec: ImprovementRecommendation,
    persona_yaml: str,
    api_key: str,
) -> PersonaUpgradePatch | None:
    """Call Claude API to generate a persona patch from a recommendation."""
    client = Anthropic(api_key=api_key)

    prompt = PATCH_PROMPT.format(
        title=rec.title,
        recommendation_type=rec.recommendation_type.value,
        description=rec.description,
        suggested_change=rec.suggested_change,
        priority=rec.priority,
        persona_yaml=persona_yaml,
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
        # Try to find JSON block in response
        json_start = raw_text.find("{")
        json_end = raw_text.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            logger.error(f"No JSON found in response for rec {rec.recommendation_id}")
            return None

        result = json.loads(raw_text[json_start:json_end])
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from response: {e}")
        return None

    patches_data = result.get("patches", [])
    rationale = result.get("rationale", "")

    if not patches_data:
        logger.warning(f"No patches generated for rec {rec.recommendation_id}")
        return None

    # Convert to PersonaFieldPatch objects
    patches = []
    for p in patches_data:
        try:
            patches.append(PersonaFieldPatch(
                operation=PatchOperation(p["operation"]),
                path=p["path"],
                value=p.get("value"),
            ))
        except (ValueError, KeyError) as e:
            logger.warning(f"Invalid patch operation: {e}")
            continue

    if not patches:
        return None

    # Determine target persona
    persona_id = rec.target_persona_ids[0] if rec.target_persona_ids else "unknown"

    return PersonaUpgradePatch(
        patch_id=f"patch-{uuid.uuid4().hex[:8]}",
        persona_id=persona_id,
        patches=patches,
        rationale=rationale,
        source_recommendation_ids=[rec.recommendation_id],
    )


def validate_patch(persona_id: str, patch: PersonaUpgradePatch) -> bool:
    """Validate a patch by applying it to a copy of the persona and checking schema.

    Uses the Academy's CLI validate command.
    """
    try:
        persona_yaml = load_persona_yaml(persona_id)
        persona_data = yaml.safe_load(persona_yaml)
    except Exception as e:
        logger.error(f"Cannot load persona for validation: {e}")
        return False

    # Apply patches to a copy
    patched = _apply_patches(persona_data, patch.patches)
    if patched is None:
        return False

    # Write to temp file and validate
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir) / persona_id
        tmpdir_path.mkdir()
        (tmpdir_path / "persona.yaml").write_text(yaml.dump(patched, default_flow_style=False))

        # Run Academy's validate command
        result = subprocess.run(
            ["npm", "run", "cli", "validate", str(tmpdir_path)],
            capture_output=True,
            text=True,
            cwd=str(ACADEMY_PATH),
        )

        if result.returncode == 0:
            logger.info(f"Patch {patch.patch_id} passes schema validation")
            return True
        else:
            logger.warning(f"Patch {patch.patch_id} fails validation: {result.stderr}")
            return False


def _apply_patches(data: dict, patches: list[PersonaFieldPatch]) -> dict | None:
    """Apply JSON Pointer patches to persona data."""
    import copy
    result = copy.deepcopy(data)

    for patch in patches:
        try:
            parts = [p for p in patch.path.split("/") if p]
            if not parts:
                continue

            if patch.operation == PatchOperation.ADD:
                _set_path(result, parts, patch.value, append=parts[-1] == "-")
            elif patch.operation == PatchOperation.REPLACE:
                _set_path(result, parts, patch.value, append=False)
            elif patch.operation == PatchOperation.REMOVE:
                _remove_path(result, parts)
        except Exception as e:
            logger.error(f"Failed to apply patch at {patch.path}: {e}")
            return None

    return result


def _set_path(data: dict, parts: list[str], value, append: bool = False) -> None:
    """Set a value at a JSON Pointer path."""
    current = data
    for i, part in enumerate(parts[:-1]):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            if part not in current:
                current[part] = {}
            current = current[part]

    last = parts[-1]
    if append and isinstance(current, dict):
        # Find the list at the parent and append
        parent_key = parts[-2] if len(parts) > 1 else None
        if isinstance(current.get(parent_key, current), list):
            current.append(value)
        elif isinstance(current, list):
            current.append(value)
    elif last == "-" and isinstance(current, list):
        current.append(value)
    elif isinstance(current, list):
        current[int(last)] = value
    elif isinstance(current, dict):
        current[last] = value


def _remove_path(data: dict, parts: list[str]) -> None:
    """Remove a value at a JSON Pointer path."""
    current = data
    for part in parts[:-1]:
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]

    last = parts[-1]
    if isinstance(current, list):
        del current[int(last)]
    elif isinstance(current, dict):
        del current[last]


def main() -> int:
    parser = argparse.ArgumentParser(description="Snow-Town Persona Upgrade Engine")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without calling Claude")
    parser.add_argument("--auto-apply", action="store_true", help="Apply valid patches directly")
    parser.add_argument("--persona", type=str, help="Process only recommendations targeting a specific persona")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Persona Upgrade Engine starting")
    logger.info("=" * 60)

    store = ContractStore()

    # Get pending recommendations
    recs = get_pending_recommendations(store, persona_filter=args.persona)
    logger.info(f"Found {len(recs)} pending persona recommendations")

    if not recs:
        logger.info("Nothing to process")
        store.close()
        return 0

    if args.dry_run:
        logger.info("DRY RUN - would process:")
        for rec in recs:
            targets = ", ".join(rec.target_persona_ids) if rec.target_persona_ids else "all"
            logger.info(f"  [{rec.priority}] {rec.title} -> {targets}")
        store.close()
        return 0

    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set")
        store.close()
        return 1

    available_personas = get_persona_ids()
    processed = 0
    failed = 0

    for rec in recs:
        targets = rec.target_persona_ids if rec.target_persona_ids else available_personas
        logger.info(f"\nProcessing: [{rec.priority}] {rec.title}")

        for persona_id in targets:
            if persona_id not in available_personas:
                logger.warning(f"  Persona '{persona_id}' not found, skipping")
                continue

            try:
                persona_yaml = load_persona_yaml(persona_id)
                patch = generate_patch(rec, persona_yaml, api_key)

                if patch is None:
                    logger.warning(f"  No patch generated for {persona_id}")
                    failed += 1
                    continue

                # Validate
                is_valid = validate_patch(persona_id, patch)
                patch.schema_valid = is_valid

                # Write to store
                store.write_patch(patch)
                logger.info(f"  Patch {patch.patch_id} written (valid={is_valid})")

                if args.auto_apply and is_valid:
                    # Apply the patch directly
                    persona_data = yaml.safe_load(persona_yaml)
                    patched = _apply_patches(persona_data, patch.patches)
                    if patched:
                        persona_path = PERSONAS_PATH / persona_id / "persona.yaml"
                        persona_path.write_text(yaml.dump(patched, default_flow_style=False))
                        store.update_patch_status(patch.patch_id, "applied")
                        logger.info(f"  Patch {patch.patch_id} auto-applied to {persona_id}")

                processed += 1

            except Exception as e:
                logger.error(f"  Error processing {persona_id}: {e}")
                failed += 1

        # Mark recommendation as processed
        store.update_recommendation_status(rec.recommendation_id, "applied")

    logger.info(f"\nResults: {processed} patches generated, {failed} failures")
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
