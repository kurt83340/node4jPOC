#!/usr/bin/env python3
"""
SessionEnd hook — filet « n'oublie rien » : snapshot d'état quand une session se ferme
SANS /handoff alors qu'elle a laissé une trace git.

Le snapshot est réinjecté au prochain démarrage (SessionStart source=startup, via
sessionstart-inject-handoff.py) puis consommé. SessionEnd ne peut PAS injecter de contexte
lui-même (event cleanup-only, doc officielle) — d'où le duo écriture-ici / injection-au-startup.

Quand NE PAS écrire (v1.5.0 — avant, le filet partait à CHAQUE fin de session : SessionEnd
passe toujours APRÈS /handoff, donc le snapshot était toujours « plus frais » que HANDOFF.md
→ fausse alerte « session fermée sans /handoff » à chaque démarrage) :
  1. HANDOFF.md mis à jour PENDANT la session (/handoff, /feature-done…) et aucun travail hors
     .claude/ après cette mise à jour → rien à rattraper ; un filet plus ancien que ce HANDOFF est
     périmé → supprimé (un filet plus récent, écrit par une session parallèle, est gardé).
  2. Session sans trace git (même HEAD, même état de l'arbre qu'au démarrage : question,
     lecture, revue…) → rien à rattraper.
  3. Hors dépôt git → pas de trace mesurable → pas de filet.
Début de session = marqueur posé par SessionStart (startup/resume/clear), à défaut la 1re
entrée datée du transcript.

Écrit : .claude/.cache/session-end-snapshot.md (non-versionné, OVERWRITE — 1 par checkout).
Multi-sessions sur le MÊME checkout : last-write-wins, assumé (c'est un filet, pas la
source de vérité ; chaque worktree a son .cache/ donc son propre filet).

Input stdin :
  {
    "session_id": "...",
    "transcript_path": "...",
    "cwd": "/path/to/project",
    "reason": "clear" | "resume" | "logout" | "prompt_input_exit" | "other"
  }
"""

import json
import os
import sys
from pathlib import Path

from snapshot_common import (build_snapshot, git_fingerprint, pop_session_start, run,
                             transcript_started_at, work_after)


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = data.get("session_id", "unknown")
    transcript_path = data.get("transcript_path", "")
    cwd = data.get("cwd", os.getcwd())
    reason = data.get("reason", "other")

    if not (Path(cwd) / ".claude").exists():
        sys.exit(0)

    cache_dir = Path(cwd) / ".claude" / ".cache"
    net = cache_dir / "session-end-snapshot.md"
    try:
        start = pop_session_start(cwd, session_id)
        started_at = start.get("t") if start else None
        if started_at is None and transcript_path:
            started_at = transcript_started_at(transcript_path)

        handoff = Path(cwd) / ".claude" / "docs" / "HANDOFF.md"
        fingerprint = git_fingerprint(cwd)
        if not fingerprint:
            sys.exit(0)  # hors dépôt git : pas de trace mesurable → pas de filet (sinon alerte à chaque démarrage)
        kind = "fin de session"
        h_mtime = handoff.stat().st_mtime if handoff.is_file() else None
        if started_at is not None and h_mtime is not None and h_mtime >= started_at:
            # HANDOFF mis à jour pendant la session (/handoff, /feature-done…) : filet seulement si du
            # travail a suivi cette mise à jour (sinon l'état est consigné).
            if not work_after(cwd, h_mtime):
                try:  # un filet plus ANCIEN que ce HANDOFF est périmé ; un plus récent (autre session) reste
                    if net.is_file() and net.stat().st_mtime <= h_mtime:
                        net.unlink()
                except OSError:
                    pass
                sys.exit(0)
            kind = "fin de session — travail APRÈS le dernier /handoff"
        elif start and start.get("git") and start["git"] == fingerprint:
            sys.exit(0)  # session sans trace git → rien à rattraper
        elif not start and not run("git status --porcelain -- . ':(exclude).claude'", cwd=cwd):
            sys.exit(0)  # sans marqueur de début (hook SessionStart absent) : arbre propre → rien à rattraper

        cache_dir.mkdir(parents=True, exist_ok=True)
        snapshot = build_snapshot(kind, reason, session_id, transcript_path, cwd)
        net.write_text(snapshot, encoding="utf-8")
    except Exception:
        pass  # filet best-effort : ne jamais gêner la fermeture de session

    sys.exit(0)


if __name__ == "__main__":
    main()
