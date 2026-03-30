#!/usr/bin/env python3
"""Human-in-the-Loop Patch Review Tool.

Review, preview, apply, or reject persona upgrade patches
before they modify persona YAML files.

Usage:
    python scripts/review_patch.py list                    # Show all proposed patches
    python scripts/review_patch.py show <patch_id>         # Show patch details + diff preview
    python scripts/review_patch.py apply <patch_id>        # Apply patch to persona YAML
    python scripts/review_patch.py reject <patch_id>       # Reject with optional notes
"""

import argparse
import copy
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from contracts.persona_upgrade_patch import PatchOperation, PersonaFieldPatch, PersonaUpgradePatch
from contracts.store import ContractStore

ACADEMY_PATH = Path.home() / "projects" / "st-agent-registry"
PERSONAS_PATH = ACADEMY_PATH / "personas"


def load_persona_yaml(persona_id: str) -> dict:
    """Load a persona's YAML as a dict."""
    path = PERSONAS_PATH / persona_id / "persona.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Persona not found: {persona_id} at {path}")
    return yaml.safe_load(path.read_text())


def apply_patches(data: dict, patches: list[PersonaFieldPatch]) -> dict | None:
    """Apply JSON Pointer patches to persona data. Returns patched copy or None on error."""
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
            print(f"  ERROR applying patch at {patch.path}: {e}")
            return None

    return result


def _set_path(data: dict, parts: list[str], value, append: bool = False) -> None:
    """Set a value at a JSON Pointer path."""
    current = data
    for part in parts[:-1]:
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            if part not in current:
                current[part] = {}
            current = current[part]

    last = parts[-1]
    if append and isinstance(current, dict):
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


def validate_persona(persona_id: str, patched_data: dict) -> bool:
    """Validate patched persona against Academy schema."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir) / persona_id
        tmpdir_path.mkdir()
        (tmpdir_path / "persona.yaml").write_text(
            yaml.dump(patched_data, default_flow_style=False, allow_unicode=True)
        )
        result = subprocess.run(
            ["npm", "run", "cli", "validate", str(tmpdir_path)],
            capture_output=True,
            text=True,
            cwd=str(ACADEMY_PATH),
        )
        return result.returncode == 0


def cmd_list(store: ContractStore) -> int:
    """List all patches with their status."""
    patches = store.query_patches(limit=10000)

    if not patches:
        print("No patches found.")
        return 0

    print(f"{'Patch ID':<20} {'Persona':<15} {'Status':<12} {'Valid':<8} {'Date'}")
    print("-" * 75)
    for p in patches:
        date_str = p.emitted_at.strftime("%Y-%m-%d")
        valid_str = "yes" if p.schema_valid else "NO"
        print(f"{p.patch_id:<20} {p.persona_id:<15} {p.status:<12} {valid_str:<8} {date_str}")

    proposed = [p for p in patches if p.status == "proposed"]
    if proposed:
        print(f"\n{len(proposed)} patch(es) awaiting review.")

    return 0


def cmd_show(store: ContractStore, patch_id: str) -> int:
    """Show patch details and a YAML diff preview."""
    patches = store.query_patches(limit=10000)
    patch = next((p for p in patches if p.patch_id == patch_id), None)

    if not patch:
        print(f"Patch '{patch_id}' not found.")
        return 1

    print(f"Patch: {patch.patch_id}")
    print(f"Persona: {patch.persona_id}")
    print(f"Status: {patch.status}")
    print(f"Schema Valid: {'yes' if patch.schema_valid else 'NO'}")
    print(f"From Version: {patch.from_version} -> {patch.to_version}")
    print(f"Emitted: {patch.emitted_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Source Recommendations: {', '.join(patch.source_recommendation_ids)}")
    print()
    print(f"Rationale: {patch.rationale}")
    print()

    # Show individual operations
    print(f"Operations ({len(patch.patches)}):")
    for i, op in enumerate(patch.patches, 1):
        print(f"  {i}. {op.operation.value} {op.path}")
        if op.value is not None:
            val_preview = yaml.dump(op.value, default_flow_style=False).strip()
            for line in val_preview.splitlines()[:10]:
                print(f"     {line}")
            if len(val_preview.splitlines()) > 10:
                print(f"     ... ({len(val_preview.splitlines())} total lines)")

    # Show diff preview
    print()
    print("=" * 60)
    print("DIFF PREVIEW")
    print("=" * 60)

    try:
        original = load_persona_yaml(patch.persona_id)
        patched = apply_patches(original, patch.patches)

        if patched is None:
            print("ERROR: Could not apply patches (see errors above)")
            return 1

        original_yaml = yaml.dump(original, default_flow_style=False, allow_unicode=True)
        patched_yaml = yaml.dump(patched, default_flow_style=False, allow_unicode=True)

        # Simple line-by-line diff
        import difflib

        diff = difflib.unified_diff(
            original_yaml.splitlines(keepends=True),
            patched_yaml.splitlines(keepends=True),
            fromfile=f"personas/{patch.persona_id}/persona.yaml (current)",
            tofile=f"personas/{patch.persona_id}/persona.yaml (patched)",
            lineterm="",
        )
        diff_text = "\n".join(diff)
        if diff_text:
            print(diff_text)
        else:
            print("(no changes detected)")

    except FileNotFoundError as e:
        print(f"WARNING: {e}")
        print("Cannot show diff preview - persona file not found.")

    return 0


def cmd_apply(store: ContractStore, patch_id: str) -> int:
    """Apply a patch to the persona YAML file."""
    patches = store.query_patches(limit=10000)
    patch = next((p for p in patches if p.patch_id == patch_id), None)

    if not patch:
        print(f"Patch '{patch_id}' not found.")
        return 1

    if patch.status != "proposed":
        print(f"Patch is '{patch.status}', not 'proposed'. Cannot apply.")
        return 1

    # Load and patch
    try:
        original = load_persona_yaml(patch.persona_id)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    patched = apply_patches(original, patch.patches)
    if patched is None:
        print("ERROR: Failed to apply patches.")
        return 1

    # Validate against schema
    print("Validating against Academy schema...")
    if not validate_persona(patch.persona_id, patched):
        print("ERROR: Patched persona fails schema validation. Aborting.")
        return 1
    print("Schema validation passed.")

    # Write patched YAML
    persona_path = PERSONAS_PATH / patch.persona_id / "persona.yaml"
    patched_yaml = yaml.dump(patched, default_flow_style=False, allow_unicode=True)
    persona_path.write_text(patched_yaml)
    print(f"Written patched persona to {persona_path}")

    # Update patch status
    store.update_patch_status(patch_id, "applied")
    print(f"Patch {patch_id} marked as 'applied'.")

    # Mark source recommendations as applied
    for rec_id in patch.source_recommendation_ids:
        store.update_recommendation_status(rec_id, "applied")
        print(f"Recommendation {rec_id} marked as 'applied'.")

    return 0


def cmd_reject(store: ContractStore, patch_id: str, notes: str | None = None) -> int:
    """Reject a patch with optional notes."""
    patches = store.query_patches(limit=10000)
    patch = next((p for p in patches if p.patch_id == patch_id), None)

    if not patch:
        print(f"Patch '{patch_id}' not found.")
        return 1

    if patch.status != "proposed":
        print(f"Patch is '{patch.status}', not 'proposed'. Cannot reject.")
        return 1

    store.update_patch_status(patch_id, "rejected")
    print(f"Patch {patch_id} marked as 'rejected'.")

    if notes:
        print(f"Notes: {notes}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Human-in-the-Loop Patch Review Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/review_patch.py list
  python scripts/review_patch.py show patch-c6495783
  python scripts/review_patch.py apply patch-c6495783
  python scripts/review_patch.py reject patch-c6495783 --notes "Not ready yet"
""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List all patches")

    show_parser = subparsers.add_parser("show", help="Show patch details")
    show_parser.add_argument("patch_id", help="Patch ID to show")

    apply_parser = subparsers.add_parser("apply", help="Apply a patch")
    apply_parser.add_argument("patch_id", help="Patch ID to apply")

    reject_parser = subparsers.add_parser("reject", help="Reject a patch")
    reject_parser.add_argument("patch_id", help="Patch ID to reject")
    reject_parser.add_argument("--notes", type=str, help="Rejection notes")

    args = parser.parse_args()

    store = ContractStore()

    try:
        if args.command == "list":
            return cmd_list(store)
        elif args.command == "show":
            return cmd_show(store, args.patch_id)
        elif args.command == "apply":
            return cmd_apply(store, args.patch_id)
        elif args.command == "reject":
            return cmd_reject(store, args.patch_id, getattr(args, "notes", None))
        else:
            parser.print_help()
            return 1
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
