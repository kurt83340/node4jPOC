#!/usr/bin/env python3
"""Helpers partagés des hooks de session (PreCompact, SessionStart, SessionEnd).

Même dossier que les hooks → `import snapshot_common` fonctionne tel quel
(sys.path[0] = dossier du script exécuté). Source unique du format de snapshot, de
l'extraction git/transcript et des marqueurs de session — ne pas dupliquer dans les hooks.
"""

import hashlib
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Entrées `type: "user"` du transcript qui ne sont PAS des messages humains. Mesuré sur de
# vrais transcripts (v1.5.0) : sans ce filtre, les « derniers messages » d'un snapshot étaient
# 3 chaînes vides (PreCompact : milieu d'une boucle d'outils, 44 entrées user sur 45 = des
# tool_result) ou « caveat / <command-name>/exit / Goodbye! » (SessionEnd).
NOISE_PREFIXES = (
    "<command-", "<local-command", "<system-reminder", "<bash-", "<task-notification",
    "[Request interrupted", "This session is being continued from a previous conversation",
    "<teammate-message", "<cross-session-message", "Another Claude session sent a message",
)

# Fichiers par-session du cache, purgés au démarrage passé ce délai (sinon 1 fichier/session
# s'accumule sans fin dans .claude/.cache/).
STALE_CACHE_GLOBS = ("codemap-injected-*.json", "handoff-size-warned-*", "handoff-age-warned-*",
                     "session-start-*.json", "handoff-snapshot-*.md")
STALE_CACHE_DAYS = 7


def run(cmd: str, cwd: str = None) -> str:
    """Exécute un shell command, retourne stdout (trimmed)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ""


def human_text(entry: dict) -> str:
    """Texte d'un message HUMAIN du transcript, ou "" (résultat d'outil, méta, commande
    locale, rappel système…)."""
    if not isinstance(entry, dict) or entry.get("type") != "user" or entry.get("isMeta") \
            or entry.get("isCompactSummary") or "toolUseResult" in entry:
        return ""
    content = (entry.get("message") or {}).get("content", "")
    if isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
            return ""
        content = " ".join(c.get("text", "") for c in content
                           if isinstance(c, dict) and c.get("type") == "text")
    text = content.strip() if isinstance(content, str) else ""
    if not text or text.startswith(NOISE_PREFIXES):
        return ""
    return text


def extract_last_user_messages(transcript_path: str, n: int = 3) -> list:
    """Extrait les n derniers messages HUMAINS du transcript JSONL (300 chars max chacun)."""
    msgs = []
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                if '"user"' not in line:  # pré-filtre bon marché (transcripts de plusieurs Mo)
                    continue
                try:
                    text = human_text(json.loads(line))
                except ValueError:
                    continue
                if text:
                    msgs.append(text[:300])
    except OSError:
        pass
    return msgs[-n:]


def transcript_started_at(transcript_path: str):
    """Horodatage (epoch) de la 1re entrée datée du transcript, ou None."""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 50:
                    break
                try:
                    ts = json.loads(line).get("timestamp")
                except (ValueError, AttributeError):
                    continue
                if isinstance(ts, str) and ts:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (OSError, ValueError):
        pass
    return None


# ── Marqueurs de session (.claude/.cache/, non versionné) ────────────────────────────────────

def cache_dir(cwd) -> Path:
    return Path(cwd) / ".claude" / ".cache"


def safe_sid(session_id) -> str:
    return re.sub(r"[^\w.-]", "_", str(session_id or "nosession"))


def git_fingerprint(cwd) -> str:
    """Empreinte de l'état git (HEAD + contenu du diff + fichiers non suivis) — sert à savoir si
    une session a laissé une trace. "" hors dépôt git. Le diff COMPLET est haché (une 2e retouche
    d'un fichier déjà modifié ne change ni `status` ni `--shortstat`) ; les non-suivis comptent
    par (chemin, taille, mtime), hors `.claude/.cache/` (les marqueurs des hooks eux-mêmes)."""
    head = run("git rev-parse HEAD", cwd=cwd)
    if not head:
        return ""
    h = hashlib.sha1()
    spec = "-- . ':(exclude).claude/.cache'"  # même si .gitignore ne l'exclut pas (brownfield)
    for part in (head, run(f"git status --porcelain {spec}", cwd=cwd),
                 run(f"git diff HEAD {spec}", cwd=cwd)):
        h.update(part.encode("utf-8", "replace") + b"\0")
    untracked = run(f"git ls-files --others --exclude-standard {spec}", cwd=cwd).splitlines()
    for rel in sorted(u for u in untracked if not u.startswith(".claude/.cache/"))[:500]:
        try:
            st = (Path(cwd) / rel).stat()
            h.update(f"{rel}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8", "replace") + b"\0")
        except OSError:
            pass
    return h.hexdigest()


def work_after(cwd, since: float) -> bool:
    """Du travail (hors .claude/ — méthode, doc, cache) a-t-il été fait APRÈS `since` (epoch) ?
    Fichiers modifiés non commités + fichiers des commits postérieurs, dont le mtime est > since.
    Un simple commit de ce qui existait déjà au /handoff ne compte pas (mtimes inchangés)."""
    files = set()
    for line in run("git status --porcelain -- . ':(exclude).claude'", cwd=cwd).splitlines():
        path = line[3:].strip().strip('"')
        files.add(path.split(" -> ")[-1])
    iso = datetime.fromtimestamp(since).strftime("%Y-%m-%d %H:%M:%S")
    for line in run(f"git log --since='{iso}' --name-only --format= -- . ':(exclude).claude'", cwd=cwd).splitlines():
        if line.strip():
            files.add(line.strip())
    for rel in files:
        try:
            if (Path(cwd) / rel).stat().st_mtime > since:
                return True
        except OSError:
            continue
    return False


def mark_session_start(cwd, session_id) -> None:
    """SessionStart : horodate le début de session + empreinte git (relus au SessionEnd)."""
    try:
        d = cache_dir(cwd)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"session-start-{safe_sid(session_id)}.json").write_text(
            json.dumps({"t": time.time(), "git": git_fingerprint(cwd)}), encoding="utf-8")
    except OSError:
        pass


def pop_session_start(cwd, session_id):
    """Lit ET retire le marqueur de début de session (dict) — None s'il manque."""
    p = cache_dir(cwd) / f"session-start-{safe_sid(session_id)}.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        p.unlink()
    except OSError:
        pass
    return data if isinstance(data, dict) else None


def purge_stale_cache(cwd, days: int = STALE_CACHE_DAYS) -> int:
    """Supprime les fichiers par-session du cache (et les marqueurs PreCompact laissés dans
    $TMPDIR par des sessions interrompues) plus vieux que `days` jours."""
    import tempfile
    d = cache_dir(cwd)
    limit, removed = time.time() - days * 86400, 0
    targets = [(Path(tempfile.gettempdir()), "claude-handoff-marker-*.json")]
    if d.is_dir():
        targets += [(d, pattern) for pattern in STALE_CACHE_GLOBS]
    for folder, pattern in targets:
        for f in folder.glob(pattern):
            try:
                if f.is_file() and f.stat().st_mtime < limit:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
    return removed


def build_snapshot(
    kind: str, label: str, session_id: str, transcript_path: str, cwd: str
) -> str:
    """Compose un snapshot markdown : git state + derniers messages humains.

    kind  : "pré-compaction" | "fin de session" (rendu dans le header)
    label : trigger PreCompact ("auto"/"manual") ou reason SessionEnd ("logout"…)
    """
    branch = run("git branch --show-current", cwd=cwd) or "unknown"
    status = run("git status --short", cwd=cwd) or "(clean)"
    log = run("git log -5 --oneline", cwd=cwd) or "(no commits)"
    user_msgs = extract_last_user_messages(transcript_path) if transcript_path else []
    now = datetime.now().strftime("%Y-%m-%d %Hh%M")

    return f"""

---

## 📸 Auto-snapshot {kind} ({label}) — {now}

**Branche** : `{branch}`
**Session ID** : `{str(session_id)[:8]}…`

### Git status
```
{status}
```

### 5 derniers commits
```
{log}
```

### Derniers messages user (extraits)
{chr(10).join(f"- {m}" for m in user_msgs) if user_msgs else "_(aucun)_"}
"""
