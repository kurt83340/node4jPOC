#!/usr/bin/env python3
"""
PreCompact hook — Snapshot d'état avant compaction (cache non-versionné, par-session).

Pattern inspiré de github.com/thepushkarp/handoff.

Trigger : avant que Claude compacte le contexte (auto à ~90% OU /compact manuel).
Action :
  1. Composer le snapshot (git state + derniers messages user) — via snapshot_common
  2. Écrire (OVERWRITE) dans .claude/.cache/handoff-snapshot-<session_id>.md — cache
     gitignored, nommé par session_id (pas de collision entre teammates partageant le
     repo), jamais appendé.
  3. Écrire marker /tmp/claude-handoff-marker-<session_id>.json pour SessionStart

Input stdin (JSON Claude Code hook event) :
  {
    "session_id": "...",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/project",
    "trigger": "auto" | "manual"   # top-level — PreCompact n'a PAS de tool_input
  }
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from snapshot_common import build_snapshot


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = data.get("session_id", "unknown")
    transcript_path = data.get("transcript_path", "")
    cwd = data.get("cwd", os.getcwd())
    # PreCompact porte "trigger" au TOP-LEVEL ("auto"|"manual"). Il n'a PAS de
    # tool_input (réservé aux events Pre/PostToolUse) — d'où le bug historique.
    trigger = data.get("trigger", "auto")

    # Snapshot écrit dans un cache NON-VERSIONNÉ (.claude/.cache/, gitignored) au lieu
    # d'être appendé au HANDOFF.md versionné (sinon bloat : +~442 o/compaction, jamais purgé).
    if not (Path(cwd) / ".claude").exists():
        sys.exit(0)
    cache_dir = Path(cwd) / ".claude" / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Nom par-session → deux teammates partageant le repo n'écrasent pas le snapshot
    # l'un de l'autre (sinon ré-injection du mauvais contexte au SessionStart).
    safe_sid = "".join(c if (c.isalnum() or c in "-_") else "_" for c in session_id)
    snapshot_path = cache_dir / f"handoff-snapshot-{safe_sid}.md"

    snapshot = build_snapshot("pré-compaction", trigger, session_id, transcript_path, cwd)

    # Overwrite (pas d'append) → le cache ne contient jamais qu'UN snapshot, le dernier.
    try:
        snapshot_path.write_text(snapshot, encoding="utf-8")
    except Exception as e:
        print(f"⚠️  Failed to write snapshot: {e}", file=sys.stderr)
        sys.exit(0)

    # Marker pour SessionStart
    now = datetime.now().strftime("%Y-%m-%d %Hh%M")
    marker_path = Path(tempfile.gettempdir()) / f"claude-handoff-marker-{session_id}.json"
    marker_path.write_text(
        json.dumps(
            {
                "needs_inject": True,
                "snapshot_path": str(snapshot_path),
                "timestamp": now,
                "trigger": trigger,
            }
        )
    )

    # Notification user (non-blocking)
    print(
        json.dumps(
            {
                "systemMessage": f"📸 Snapshot pré-compaction écrit dans .claude/.cache/ (trigger: {trigger}). HANDOFF.md versionné non touché. Re-injection au prochain start."
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
