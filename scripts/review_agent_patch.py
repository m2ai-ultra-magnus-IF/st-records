#!/usr/bin/env python3
"""Human-in-the-Loop Agent Patch Review Tool.

Review, preview, apply, or reject agent upgrade patches
before they modify agent CLAUDE.md files.

Usage:
    python scripts/review_agent_patch.py list                    # Show all agent patches
    python scripts/review_agent_patch.py show <patch_id>         # Show patch details + diff preview
    python scripts/review_agent_patch.py approve <patch_id>      # Approve patch (for Metroplex Gate 3)
    python scripts/review_agent_patch.py reject <patch_id>       # Reject with optional notes
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from contracts.agent_upgrade_patch import AgentUpgradePatch
from contracts.store import ContractStore

REGISTRY_PATH = Path.home() / "projects" / "st-agent-registry"
AGENTS_PATH = REGISTRY_PATH / "agents"


def load_agent_claude_md(agent_id: str) -> str:
    """Load an agent's CLAUDE.md content."""
    path = AGENTS_PATH / agent_id / "CLAUDE.md"
    if not path.exists():
        raise FileNotFoundError(f"Agent CLAUDE.md not found: {agent_id} at {path}")
    return path.read_text()


def preview_patch(claude_md: str, patch: AgentUpgradePatch) -> str | None:
    """Preview what applying a patch would produce.

    Returns the patched CLAUDE.md content, or None on error.
    """
    if patch.operation == "add":
        if patch.section == "NEW":
            # Append new section at end
            return claude_md.rstrip() + "\n\n" + (patch.value or "") + "\n"
        else:
            # Find section and append content
            pattern = re.compile(
                rf'^({re.escape(patch.section)}\s*\n)(.*?)(?=^##|\Z)',
                re.MULTILINE | re.DOTALL,
            )
            match = pattern.search(claude_md)
            if not match:
                print(f"  WARNING: Section '{patch.section}' not found in CLAUDE.md")
                return None
            insert_pos = match.end()
            return claude_md[:insert_pos].rstrip() + "\n" + (patch.value or "") + "\n" + claude_md[insert_pos:]

    elif patch.operation == "replace":
        pattern = re.compile(
            rf'^({re.escape(patch.section)}\s*\n)(.*?)(?=^##|\Z)',
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(claude_md)
        if not match:
            print(f"  WARNING: Section '{patch.section}' not found in CLAUDE.md")
            return None
        return claude_md[:match.start(2)] + (patch.value or "") + "\n" + claude_md[match.end():]

    elif patch.operation == "remove":
        pattern = re.compile(
            rf'^{re.escape(patch.section)}\s*\n.*?(?=^##|\Z)',
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(claude_md)
        if not match:
            print(f"  WARNING: Section '{patch.section}' not found in CLAUDE.md")
            return None
        return claude_md[:match.start()] + claude_md[match.end():]

    return None


def cmd_list(store: ContractStore) -> int:
    """List all agent patches with their status."""
    patches = store.query_agent_patches(limit=10000)

    if not patches:
        print("No agent patches found.")
        return 0

    print(f"{'Patch ID':<28} {'Agent':<14} {'Target':<12} {'Op':<10} {'Status':<12} {'Date'}")
    print("-" * 90)
    for p in patches:
        date_str = p.emitted_at.strftime("%Y-%m-%d")
        print(f"{p.patch_id:<28} {p.agent_id:<14} {p.target:<12} {p.operation:<10} {p.status:<12} {date_str}")

    proposed = [p for p in patches if p.status == "proposed"]
    if proposed:
        print(f"\n{len(proposed)} patch(es) awaiting review.")

    return 0


def cmd_show(store: ContractStore, patch_id: str) -> int:
    """Show patch details and a diff preview."""
    patches = store.query_agent_patches(limit=10000)
    patch = next((p for p in patches if p.patch_id == patch_id), None)

    if not patch:
        print(f"Patch '{patch_id}' not found.")
        return 1

    print(f"Patch: {patch.patch_id}")
    print(f"Agent: {patch.agent_id}")
    print(f"Target: {patch.target}")
    print(f"Section: {patch.section}")
    print(f"Operation: {patch.operation}")
    print(f"Status: {patch.status}")
    print(f"Emitted: {patch.emitted_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Source Recommendations: {', '.join(patch.source_recommendation_ids)}")
    print()
    print(f"Rationale: {patch.rationale}")

    if patch.value:
        print()
        print("Value:")
        for line in patch.value.splitlines()[:20]:
            print(f"  {line}")
        if len(patch.value.splitlines()) > 20:
            print(f"  ... ({len(patch.value.splitlines())} total lines)")

    # Show diff preview
    print()
    print("=" * 60)
    print("DIFF PREVIEW")
    print("=" * 60)

    try:
        original = load_agent_claude_md(patch.agent_id)
        patched = preview_patch(original, patch)

        if patched is None:
            print("ERROR: Could not preview patch (see warnings above)")
            return 1

        import difflib

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"agents/{patch.agent_id}/CLAUDE.md (current)",
            tofile=f"agents/{patch.agent_id}/CLAUDE.md (patched)",
            lineterm="",
        )
        diff_text = "\n".join(diff)
        if diff_text:
            print(diff_text)
        else:
            print("(no changes detected)")

    except FileNotFoundError as e:
        print(f"WARNING: {e}")
        print("Cannot show diff preview - agent CLAUDE.md not found.")

    return 0


def cmd_approve(store: ContractStore, patch_id: str) -> int:
    """Approve a patch (marks as 'approved' for Metroplex Gate 3 to apply)."""
    patches = store.query_agent_patches(limit=10000)
    patch = next((p for p in patches if p.patch_id == patch_id), None)

    if not patch:
        print(f"Patch '{patch_id}' not found.")
        return 1

    if patch.status != "proposed":
        print(f"Patch is '{patch.status}', not 'proposed'. Cannot approve.")
        return 1

    store.update_agent_patch_status(patch_id, "approved")
    print(f"Patch {patch_id} marked as 'approved'.")
    print("Metroplex Gate 3 will apply it to the registry and sync to runtime.")

    return 0


def cmd_reject(store: ContractStore, patch_id: str, notes: str | None = None) -> int:
    """Reject a patch with optional notes."""
    patches = store.query_agent_patches(limit=10000)
    patch = next((p for p in patches if p.patch_id == patch_id), None)

    if not patch:
        print(f"Patch '{patch_id}' not found.")
        return 1

    if patch.status != "proposed":
        print(f"Patch is '{patch.status}', not 'proposed'. Cannot reject.")
        return 1

    store.update_agent_patch_status(patch_id, "rejected")
    print(f"Patch {patch_id} marked as 'rejected'.")

    if notes:
        print(f"Notes: {notes}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Human-in-the-Loop Agent Patch Review Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/review_agent_patch.py list
  python scripts/review_agent_patch.py show agent-patch-c6495783
  python scripts/review_agent_patch.py approve agent-patch-c6495783
  python scripts/review_agent_patch.py reject agent-patch-c6495783 --notes "Not ready yet"
""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List all agent patches")

    show_parser = subparsers.add_parser("show", help="Show patch details")
    show_parser.add_argument("patch_id", help="Patch ID to show")

    approve_parser = subparsers.add_parser("approve", help="Approve a patch")
    approve_parser.add_argument("patch_id", help="Patch ID to approve")

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
        elif args.command == "approve":
            return cmd_approve(store, args.patch_id)
        elif args.command == "reject":
            return cmd_reject(store, args.patch_id, getattr(args, "notes", None))
        else:
            parser.print_help()
            return 1
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
