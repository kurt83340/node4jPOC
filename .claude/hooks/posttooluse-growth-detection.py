#!/usr/bin/env python3
"""
PostToolUse hook (matcher: "Edit|Write") — Détecte les growth triggers et flag.

Trigger : après chaque Edit/Write sur un fichier.
Action :
  1. Scan le contenu écrit pour détecter mots-clés growth (API_KEY, deploy, prod, etc.)
  2. Si trigger détecté ET fichier doc cible manquant/vide → append à .claude/.growth-suggestions.md
  3. Non-blocking : juste flag pour /doc-health

Input stdin :
  {
    "tool_name": "Edit" | "Write" | "MultiEdit",
    "tool_input": {"file_path": "...", "content"/"new_string"/"edits": ...},
    "cwd": "/path/to/project"
  }
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Triggers : (regex, suggestion)
GROWTH_TRIGGERS = [
    (
        re.compile(r"\b(API_KEY|api_key|OAuth|oauth|token|credentials|secret)\b", re.IGNORECASE),
        ("ACCESS.md", "Credentials/API détectés → enrichir ACCESS.md"),
    ),
    (
        re.compile(r"\b(deploy|production|prod|incident|rollback|outage)\b", re.IGNORECASE),
        ("RUNBOOK.md", "Mentions deploy/prod détectées → créer/enrichir RUNBOOK.md"),
    ),
    # NB : pas de trigger STAKEHOLDERS.md — la doctrine du template dit explicitement
    # de NE PAS créer ce fichier pour < 5 personnes (cf. template-maintenance.md).
]


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    # Write → content ; Edit → new_string ; MultiEdit → edits[].new_string (concaténés)
    content = tool_input.get("content") or tool_input.get("new_string", "")
    if not content and isinstance(tool_input.get("edits"), list):
        content = "\n".join(
            e.get("new_string", "") for e in tool_input["edits"] if isinstance(e, dict)
        )

    if not content or not file_path:
        sys.exit(0)

    # Skip tout ce qui vit sous .claude/ — docs, rules, skills, hooks, plans,
    # et .growth-suggestions.md lui-même (auto-flag au tri) : ces fichiers parlent
    # légitimement de credentials/deploy/prod sans être du code projet.
    # (Guard élargi v1.3.2 — battle-testé sur projet généré après 3 purges de faux positifs.)
    if "/.claude/" in file_path or file_path.startswith(".claude/") \
            or file_path.endswith(".growth-suggestions.md"):
        sys.exit(0)

    cwd = data.get("cwd", os.getcwd())
    suggestions_path = Path(cwd) / ".claude" / ".growth-suggestions.md"
    suggestions_path.parent.mkdir(exist_ok=True, parents=True)

    # Chemin RELATIF au projet (sinon on logge des chemins absolus hors-projet, non actionnables)
    try:
        rel_source = str(Path(file_path).resolve().relative_to(Path(cwd).resolve()))
    except Exception:
        rel_source = os.path.basename(file_path)

    detected = []
    for pattern, (target_file, message) in GROWTH_TRIGGERS:
        if pattern.search(content):
            # Check si target_file existe et n'est pas vide
            target = Path(cwd) / ".claude" / "docs" / target_file
            if not target.exists() or target.stat().st_size < 500:
                detected.append((target_file, message, rel_source))

    if not detected:
        sys.exit(0)

    # Append au fichier growth-suggestions (sans duplicates)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    existing = ""
    if suggestions_path.exists():
        try:
            existing = suggestions_path.read_text(encoding="utf-8")
        except Exception:
            pass

    new_entries = []
    seen_in_run = set()
    for target_file, message, source in detected:
        # Dédup par (source, message) SANS le timestamp — sinon ré-émission à chaque
        # minute pour le même fichier/trigger. La signature suffit à identifier le flag.
        signature = f"source: `{source}` → {message}"
        if signature in existing or signature in seen_in_run:
            continue
        seen_in_run.add(signature)
        new_entries.append(f"- **{now}** | {signature}\n")

    if new_entries:
        header = ""
        if not existing:
            header = """# Growth Suggestions (auto-detected)

> Triggers détectés par hook PostToolUse. Review hebdo via `/doc-health`.

"""
        try:
            suggestions_path.write_text(existing + header + "".join(new_entries), encoding="utf-8")
        except Exception:
            pass

    # Notification non-blocking (visible dans Claude UI)
    if new_entries:
        first_msg = detected[0][1]
        print(
            json.dumps(
                {
                    "systemMessage": f"💡 Growth trigger : {first_msg}. Flag dans .claude/.growth-suggestions.md"
                }
            )
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
