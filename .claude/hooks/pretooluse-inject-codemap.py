#!/usr/bin/env python3
"""
PreToolUse hook (matcher: "Edit|Write") — injecte les GOTCHAS qui ciblent le fichier édité.

Pourquoi : Claude retrouve seul le rôle/les imports/les tests d'un fichier (agentic search), et
les règles de couplage + l'intention sont DÉJÀ en contexte (`code-map.md` est @-importé par le
CLAUDE.md racine, relu après chaque compaction). Ce qu'il n'a PAS : les gotchas, rangés dans
`code-map-gotchas.md` (non auto-chargé, budget v1.4). C'est ça — et seulement ça — qu'on injecte.

Livraison (doc hooks) : l'`additionalContext` d'un PreToolUse arrive « alongside the tool
result », donc juste APRÈS l'édition — c'est un rattrapage immédiat (Claude corrige dans la
foulée), pas un blocage préventif.

Budget : une injection par (session, fichier) — marker `.claude/.cache/codemap-injected-<sid>.json`,
effacé par SessionStart(compact) → ré-armé après chaque compaction. Plus de réinjection des
règles de couplage (v1.5.0 : doublon de code-map.md, déjà en contexte).

Ciblage : une entrée cible un fichier en citant en backticks un chemin, un nom de fichier ou un
dossier (ou via son heading `###`) ; les entrées sous un heading « Globaux » valent pour toute
édition de code. Projet < 1.4 sans code-map-gotchas.md → § Gotchas de code-map.md.

Ordre et budget : la plus spécifique d'abord — chemin exact / nom du fichier, puis le dossier le plus
profond, puis les dossiers parents, les Globaux en DERNIER — et la coupe à MAX_CHARS tombe entre deux
entrées entières, avec « N gotcha(s) non injecté(s) ». Vécu : 53 Globaux migrés en tête de fichier,
coupe à 2 500 caractères → les gotchas propres au fichier n'arrivaient jamais ; et un gotcha général
sur `src/adapter/` passait avant ceux de `src/adapter/ocr/`, que la coupe faisait tomber.

Fichiers concernés (v1.5.0) : tout fichier DU PROJET hors `.claude/` — plus de liste fixe
src/tests/lib/app (ratait packages/, backend/…). Docs/config (.md, .json, .yaml…) : uniquement les
gotchas qui les ciblent explicitement (workflows n8n en .json), jamais les Globaux. Les entrées du
gabarit encore en `{{…}}` ne sont jamais injectées.
Input stdin : {"session_id": "...", "tool_name": "Edit"|"Write", "tool_input": {"file_path": "..."}, "cwd": "..."}
Output JSON : {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "..."}}
Non-bloquant : toute erreur → exit 0 silencieux.
"""

import json
import os
import re
import sys
from pathlib import Path

MAX_CHARS = 2500            # cap de l'additionalContext (doc : 10k max)
NON_CODE_EXT = (".md", ".mdx", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
                ".lock", ".csv", ".log", ".env", ".example")


def extract_section(text: str, title: str) -> str:
    """Capture « ## <title> … » jusqu'au prochain « ## » ou la fin."""
    m = re.search(rf"(##\s+{re.escape(title)}.*?)(?=\n##\s|\Z)", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def gotcha_entries(text: str):
    """Découpe un texte de gotchas en (heading_courant, entrée). Une entrée = un bullet
    (`- ` / `* ` / `⚠️`) + ses lignes de continuation indentées. Les headings `#`/`##`/`###`
    changent le groupe courant (un heading peut lui-même cibler un dossier/fichier)."""
    entries, heading, cur = [], "", []
    for line in text.split("\n"):
        if re.match(r"#{1,4} ", line):
            if cur:
                entries.append((heading, "\n".join(cur)))
                cur = []
            heading = line
            continue
        if re.match(r"\s*([-*]|⚠️)\s", line):
            if cur:
                entries.append((heading, "\n".join(cur)))
            cur = [line.rstrip()]
        elif cur and line.startswith((" ", "\t")) and line.strip():
            cur.append(line.rstrip())
        elif cur and not line.strip():
            entries.append((heading, "\n".join(cur)))
            cur = []
    if cur:
        entries.append((heading, "\n".join(cur)))
    return entries


def path_tokens(s: str):
    """Tokens en backticks qui ressemblent à un chemin ou un nom de fichier (`src/x/`, `x.py`)."""
    toks = re.findall(r"`([^`\n]+)`", s)
    return [t.strip() for t in toks if ("/" in t or "." in t) and " " not in t.strip()]


def match_score(tokens, rel: str, name: str) -> int:
    """Spécificité du meilleur token qui cible `rel` (0 = ne le cible pas). Chemin exact ou nom du
    fichier > dossier (d'autant plus spécifique qu'il est profond) > simple fragment du chemin."""
    rel_n = rel.replace("\\", "/")
    best = 0
    for t in tokens:
        t = t.lstrip("./")
        if not t:
            continue
        depth = len([s for s in t.strip("/").split("/") if s])
        if rel_n == t or rel_n.endswith("/" + t) or t == name:
            score = 1000 + depth  # le fichier lui-même
        elif ("/" + rel_n).startswith("/" + t.rstrip("/") + "/") or ("/" + t.rstrip("/") + "/") in ("/" + rel_n):
            score = 100 + depth   # un dossier qui le contient : plus profond = plus spécifique
        elif t in rel_n:
            score = 1             # fragment (ancien critère, gardé pour ne rien perdre)
        else:
            continue
        best = max(best, score)
    return best


def heading_tokens(heading: str):
    """Un heading cible par backticks (`src/x/`) OU par token nu contenant un « / » (### src/jobs/)."""
    bare = [t for t in heading.lstrip("#").split() if "/" in t and "`" not in t]
    return path_tokens(heading) + bare


def targeted_entries(text: str, rel: str, name: str, with_globals: bool = True):
    """Entrées qui s'appliquent à `rel`, de la plus spécifique à la moins spécifique (Globaux en
    dernier) ; à spécificité égale, l'ordre du fichier."""
    scored = []
    for i, (heading, entry) in enumerate(gotcha_entries(text)):
        if re.search(r"\{\{[^}]*\}\}", entry):
            continue  # entrée du gabarit jamais remplie (« ⚠️ {{Piège transversal…}} ») → bruit
        if re.search(r"globa", heading, re.IGNORECASE):
            if with_globals:
                scored.append((0, i, entry))
            continue
        score = match_score(heading_tokens(heading) + path_tokens(entry), rel, name)
        if score:
            scored.append((score, i, entry))
    return [e for _, _, e in sorted(scored, key=lambda x: (-x[0], x[1]))]


def fit(entries, budget: int):
    """Entrées entières jusqu'au budget ; (texte, nombre d'entrées laissées de côté). Une 1re entrée
    plus longue que le budget est tronquée plutôt que perdue."""
    out, used = [], 0
    for k, e in enumerate(entries):
        cost = len(e) + (1 if out else 0)
        if used + cost > budget:
            if not out:
                return e[:budget].rstrip() + " […]", len(entries) - 1
            return "\n".join(out), len(entries) - k
        out.append(e)
        used += cost
    return "\n".join(out), 0


def load_marker(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("files"), list):
            return d
    except Exception:
        pass
    return {"files": []}


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("tool_name", "") not in ("Edit", "Write", "MultiEdit"):
        sys.exit(0)
    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Racine = CLAUDE_PROJECT_DIR (fixe pour la session), pas le cwd du payload, qui suit les `cd`
    # (même règle que posttooluse-growth-detection depuis la PR n°2).
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    try:
        rel = os.path.relpath(file_path, cwd).replace("\\", "/")
    except ValueError:
        sys.exit(0)
    # Gate : fichier DU PROJET (chemin relatif — un projet rangé sous un dossier parent nommé
    # « src/ » ne doit pas tout matcher), hors méthode (.claude/). Docs/config (.md, .json…) :
    # seulement les gotchas qui les CIBLENT explicitement (ex. workflows n8n en .json = le code
    # d'un projet automation-n8n) — jamais les Globaux, réservés au code.
    if rel.startswith("../") or rel == ".." or rel.startswith(".claude/"):
        sys.exit(0)
    is_code = not file_path.lower().endswith(NON_CODE_EXT)

    docs = cwd / ".claude" / "docs"
    gotchas_file = docs / "code-map-gotchas.md"
    codemap = docs / "code-map.md"
    try:
        if gotchas_file.is_file():
            gsrc = gotchas_file.read_text(encoding="utf-8")
        elif codemap.is_file():  # projet < 1.4 : gotchas encore dans code-map.md
            gsrc = extract_section(codemap.read_text(encoding="utf-8"), "Gotchas")
        else:
            sys.exit(0)
    except OSError:
        sys.exit(0)

    session_id = re.sub(r"[^\w.-]", "_", str(data.get("session_id", "nosession")))
    marker_path = cwd / ".claude" / ".cache" / f"codemap-injected-{session_id}.json"
    marker = load_marker(marker_path)
    if rel in marker["files"]:
        sys.exit(0)  # déjà injecté pour ce fichier dans cette session

    entries = targeted_entries(gsrc, rel, Path(file_path).name, with_globals=is_code) if gsrc else []
    marker["files"].append(rel)
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
    except Exception:
        pass

    if not entries:
        sys.exit(0)
    gotchas, left = fit(entries, MAX_CHARS)
    more = (f"\n\n… {left} gotcha(s) de plus pour ce fichier non injecté(s) (budget {MAX_CHARS} car.) "
            "→ lis `.claude/docs/code-map-gotchas.md`.") if left else ""

    context = f"""## ⚠️ Gotchas ciblant `{rel}` (code-map-gotchas.md)

{gotchas}{more}

→ Pièges déjà payés sur ce fichier/cette zone : vérifie que ton édition les respecte, corrige
dans la foulée sinon. (Injecté une fois par session et par fichier — budget contexte.)"""

    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                              "additionalContext": context}}))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
