#!/usr/bin/env python3
"""context-budget.py — chiffre la surface de contexte AUTO-CHARGÉE au démarrage d'une session
Claude Code (ce qu'elle lit SANS qu'on le lui demande) et pointe les coupables.

Auto-chargé (doc Claude Code — memory.md) :
  · `CLAUDE.md` racine (+ `CLAUDE.local.md`) et ses `@-imports` (récursifs, ≤ 4 niveaux,
    chemins relatifs au fichier importeur)
  · `.claude/CLAUDE.md` et ses `@-imports`
  · toutes les rules `.claude/rules/**/*.md` SANS frontmatter `paths:` (celles avec `paths:`
    ne se chargent que quand Claude lit un fichier qui matche)
  · hors projet : `~/.claude/CLAUDE.md` (user) et `MEMORY.md` de l'auto-memory
À la demande : rules scopées, corps des skills (seul le frontmatter est listé), tout le reste.

Estimation : **tokens ≈ chars / 2** — calibrée le 2026-09-08 sur du markdown français (tables,
emoji, chemins) : 0,40–0,52 tok/char mesurés via `claude -p --output-format json` (usage du
1er tour). `chars/4` sous-estime d'un facteur 2.

Usage : python3 .claude/skills/doc-health/scripts/context-budget.py [--root DIR] [--max TOK]
                                                                     [--json] [--no-user]
  --max TOK : seuil sur le total PROJET (hors user/mémoire) → exit 1 si dépassé
  exit 0 = OK · 1 = seuil dépassé · 2 = erreur
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

IMPORT_RE = re.compile(r"(?<![\w`@/])@((?:\.\./|\./)?\.?[\w][\w./-]*)")  # .claude/… accepté
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
BIG_FILE_TOK = 4000  # au-delà, un fichier auto-chargé mérite un remède


def est(chars: int) -> int:
    return chars // 2


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def has_paths_frontmatter(text: str) -> bool:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    return bool(m and re.search(r"^paths\s*:", m.group(1), re.M))


def fenced_mask(lines):
    mask, fence = [], None
    for line in lines:
        m = FENCE_RE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)[0]
            mask.append(m is not None)
        else:
            mask.append(True)
            if m and m.group(1)[0] == fence:
                fence = None
    return mask


def find_imports(text: str, base: Path):
    """@-imports d'un fichier mémoire (hors blocs fencés / spans inline), résolus relativement
    au fichier importeur. Ne garde que les FICHIERS existants (un import de dossier est ignoré
    par Claude Code)."""
    out = []
    lines = text.split("\n")
    for line, in_code in zip(lines, fenced_mask(lines)):
        if in_code:
            continue
        clean = re.sub(r"`[^`]*`", "", line)
        for m in IMPORT_RE.finditer(clean):
            tok = m.group(1).rstrip(".,;:)")
            p = (base.parent / tok)
            if p.is_file():
                out.append(p.resolve())
    return out


def remedy(rel: str, tok: int, scoped_import: bool) -> str:
    if scoped_import:
        return "rule scopée `paths:` importée en @ → scoping court-circuité : retirer le @ (lien simple)"
    if tok < BIG_FILE_TOK:
        return ""
    n = rel.lower()
    if "handoff" in n:
        return "HANDOFF > 40 lignes ? journal append-only → HANDOFF-journal.md (non importé)"
    if "code-map" in n:
        return "gotchas → code-map-gotchas.md (injectés par le hook, ciblés) ; « Quand mettre à jour » = 3 lignes"
    if "roadmap" in n:
        return "dashboard : lien simple, pas @ (les skills le lisent explicitement)"
    return "scinder : garder ici l'état courant, archiver le reste dans un fichier lu à la demande"


def collect(root: Path, with_user: bool):
    rows, seen = [], set()

    def add(p: Path, kind: str, depth: int, via: str = ""):
        rp = p.resolve()
        if rp in seen:
            return
        seen.add(rp)
        text = read(rp)
        try:
            rel = str(rp.relative_to(root.resolve()))
        except ValueError:
            rel = str(rp).replace(str(Path.home()), "~")
        scoped_import = kind == "import" and has_paths_frontmatter(text)
        tok = est(len(text))
        rows.append({"path": rel, "kind": kind, "chars": len(text), "tok": tok,
                     "via": via, "remedy": remedy(rel, tok, scoped_import),
                     "scoped_import": scoped_import})
        if depth < 4:
            for imp in find_imports(text, rp):
                add(imp, "import", depth + 1, rel)

    for name in ("CLAUDE.md", "CLAUDE.local.md"):
        p = root / name
        if p.is_file():
            add(p, "index", 0)
    p = root / ".claude" / "CLAUDE.md"
    if p.is_file():
        add(p, "index", 0)
    rules_dir = root / ".claude" / "rules"
    on_demand = []
    if rules_dir.is_dir():
        for r in sorted(rules_dir.rglob("*.md")):
            t = read(r)
            rel = str(r.relative_to(root))
            if has_paths_frontmatter(t):
                on_demand.append({"path": rel, "tok": est(len(t))})
            else:
                add(r, "rule", 0)
    skills_dir = root / ".claude" / "skills"
    skills_tok = 0
    if skills_dir.is_dir():
        for s in skills_dir.glob("*/SKILL.md"):
            m = re.match(r"---\n(.*?)\n---", read(s), re.S)
            if not m:
                continue
            fm = m.group(1)
            # Doc skills : seuls nom + description (+ when_to_use) sont listés ; un skill en
            # `disable-model-invocation: true` n'a PAS sa description en contexte.
            if re.search(r"^disable-model-invocation:\s*true\s*$", fm, re.M):
                continue
            listed = [l for l in fm.split("\n") if re.match(r"(name|description|when_to_use)\s*:", l)]
            skills_tok += est(len("\n".join(listed)))

    user_rows = []
    if with_user:
        u = Path.home() / ".claude" / "CLAUDE.md"
        if u.is_file():
            ut = read(u)
            user_rows.append({"path": "~/.claude/CLAUDE.md", "tok": est(len(ut))})
            for imp in find_imports(ut, u):
                user_rows.append({"path": str(imp).replace(str(Path.home()), "~"), "tok": est(len(read(imp)))})
        slug = re.sub(r"[/.]", "-", str(root.resolve()))
        mem = Path.home() / ".claude" / "projects" / slug / "memory" / "MEMORY.md"
        if mem.is_file():
            user_rows.append({"path": "auto-memory MEMORY.md", "tok": est(len(read(mem)))})
    return rows, on_demand, skills_tok, user_rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="racine du projet (défaut : cwd)")
    ap.add_argument("--max", type=int, default=None, help="seuil tokens (total projet) → exit 1 si dépassé")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-user", action="store_true", help="ignorer ~/.claude/CLAUDE.md et l'auto-memory")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"❌ racine introuvable : {root}", file=sys.stderr)
        return 2

    rows, on_demand, skills_tok, user_rows = collect(root, not a.no_user)
    total = sum(r["tok"] for r in rows)
    user_total = sum(r["tok"] for r in user_rows)
    over = a.max is not None and total > a.max

    if a.json:
        print(json.dumps({"root": str(root), "total_tok": total, "user_tok": user_total,
                          "skills_frontmatter_tok": skills_tok, "max": a.max, "over": over,
                          "files": rows, "on_demand_rules": on_demand, "user": user_rows},
                         ensure_ascii=False, indent=2))
        return 1 if over else 0

    print(f"📏 Contexte auto-chargé au démarrage — {root}\n   (tokens ≈ chars/2, calibré markdown FR — ±20 %)\n")
    for r in sorted(rows, key=lambda x: -x["tok"]):
        flag = "🔴" if r["tok"] >= BIG_FILE_TOK or r["scoped_import"] else "  "
        via = f"  ← @ depuis {r['via']}" if r["via"] else ""
        print(f"{flag} {r['tok']:>7} tok  {r['path']}{via}")
        if r["remedy"]:
            print(f"        → {r['remedy']}")
    print(f"\n   {'─' * 60}\n   TOTAL projet : {total} tok" + (f"  (seuil {a.max})" if a.max else ""))
    if user_rows:
        for r in user_rows:
            print(f"   {r['tok']:>7} tok  {r['path']}  (user, hors projet)")
        print(f"   + user/mémoire : {user_total} tok")
    if skills_tok:
        print(f"   + listing skills (nom + description, hors disable-model-invocation) : ~{skills_tok} tok")
    if on_demand:
        print("\n   À la demande (rules scopées `paths:` — NON chargées au démarrage) :")
        for r in on_demand:
            print(f"     {r['tok']:>7} tok  {r['path']}")
    if over:
        print(f"\n🔴 Seuil dépassé ({total} > {a.max}) — traite les lignes 🔴 ci-dessus "
              "(projet < v1.4 : slim-context.py du template, --dry-run d'abord).")
    elif a.max:
        print(f"\n✅ Sous le seuil ({total} ≤ {a.max}).")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
