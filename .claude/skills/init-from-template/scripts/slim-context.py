#!/usr/bin/env python3
"""slim-context.py — migre un projet généré (< v1.4.0) vers le budget de contexte v1.4.

Mesuré 2026-09-08 sur un projet d'un mois : 144k tokens au 1er tour, dont 86k pour les 3 docs
auto-chargées sans borne (journal HANDOFF, gotchas code-map, ROADMAP) et 12k pour une rule
scopée `paths:` ré-importée en `@`. Après migration : 59,8k (−58 %).

Étapes — toutes IDEMPOTENTES (sautées si déjà faites), aucune perte de contenu (on déplace) :
  1. `CLAUDE.md` + `.claude/CLAUDE.md` : tout `@-import` d'une rule scopée `paths:` → lien simple
     (le scoping reprend ses droits : la rule se charge quand on touche ses fichiers)
  2. `.claude/docs/HANDOFF.md` : § Journal (append-only) → `HANDOFF-journal.md` (non importé) + pointeur
  3. `.claude/docs/code-map.md` : § Gotchas → `code-map-gotchas.md` (injecté par le hook, ciblé) + pointeur
  4. `CLAUDE.md` racine : `@.claude/docs/ROADMAP.md` → lien simple (dashboard lu par les skills)
  5. Fichiers v1.4 copiés depuis le template (sauf --no-template-files) — seulement s'ils
     existent déjà dans le projet (pas de greffe) : rule `agent-teams.md` (version courte ;
     l'ancienne → `.claude/.cache/agent-teams.md.pre-1.4`), hooks `pretooluse-inject-codemap.py`
     + `sessionstart-inject-handoff.py`, et `doc-health/scripts/context-budget.py` (si /doc-health présent)

Usage : python3 <template>/.claude/skills/init-from-template/scripts/slim-context.py --root <projet>
            [--dry-run] [--no-template-files] [--template <racine template>]
Puis : python3 .claude/skills/doc-health/scripts/context-budget.py (dans le projet) pour vérifier.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
DRY = False


def log(msg):
    print(("[DRY] " if DRY else "") + msg)


def write(p: Path, text: str):
    if not DRY:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


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


def has_paths_frontmatter(text: str) -> bool:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    return bool(m and re.search(r"^paths\s*:", m.group(1), re.M))


def split_section(text: str, title_prefix: str, skip_prefix: str = None):
    """(avant, section, après) pour le 1er heading `## <title_prefix>…` HORS bloc fencé (et ne
    commençant pas par `skip_prefix`) ; la section court jusqu'au prochain `## ` hors fence."""
    lines = text.split("\n")
    mask = fenced_mask(lines)
    start = next((i for i, l in enumerate(lines)
                  if not mask[i] and re.match(rf"##\s+{re.escape(title_prefix)}", l)
                  and not (skip_prefix and l.startswith(skip_prefix))), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines))
                if not mask[i] and re.match(r"#{1,2} ", lines[i])), len(lines))
    return "\n".join(lines[:start]).rstrip("\n"), "\n".join(lines[start:end]).rstrip("\n"), "\n".join(lines[end:])


def entries_of(section: str) -> str:
    """Corps d'une section sans sa ligne de heading."""
    return section.split("\n", 1)[1].strip("\n") if "\n" in section else ""


# ── Étape 1 : @-imports de rules scopées ───────────────────────────────────────────────────
def step_unimport_scoped_rules(root: Path) -> None:
    for rel in ("CLAUDE.md", ".claude/CLAUDE.md"):
        p = root / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        lines = text.split("\n")
        mask = fenced_mask(lines)
        changed = []
        for i, line in enumerate(lines):
            if mask[i]:
                continue
            for m in re.finditer(r"(?<![\w`@/])@((?:\.\./|\./)?\.?[\w][\w./-]*\.md)", line):
                tok = m.group(1)
                target = (p.parent / tok)
                if target.is_file() and has_paths_frontmatter(target.read_text(encoding="utf-8")):
                    lines[i] = lines[i].replace("@" + tok, f"[{tok}]({tok})")
                    changed.append(tok)
        if changed:
            write(p, "\n".join(lines))
            log(f"✅ 1. {rel} : @-import de rule scopée → lien simple ({', '.join(changed)})")
        else:
            log(f"⏭ 1. {rel} : aucun @-import de rule scopée")


# ── Étape 2 : Journal HANDOFF ───────────────────────────────────────────────────────────────
JOURNAL_HEADER = """# Journal HANDOFF — append-only

> 1 ligne par session, ajoutée par `/handoff`, **jamais réécrite**. Fichier **non auto-chargé**
> (budget contexte v1.4) : lu à la demande quand il faut reconstituer l'arc du projet.
> L'état courant vit dans [HANDOFF.md](HANDOFF.md).

## Journal

"""
JOURNAL_POINTER = "→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé."


def step_handoff_journal(root: Path) -> None:
    ho = root / ".claude" / "docs" / "HANDOFF.md"
    jo = root / ".claude" / "docs" / "HANDOFF-journal.md"
    if not ho.is_file():
        log("⏭ 2. HANDOFF.md absent")
        return
    text = ho.read_text(encoding="utf-8")
    parts = split_section(text, "Journal")
    if parts is None:
        log("⏭ 2. HANDOFF.md : pas de § Journal" + ("" if "HANDOFF-journal.md" in text else " (pointeur ajouté)"))
        if "HANDOFF-journal.md" not in text:
            write(ho, text.rstrip("\n") + "\n\n" + JOURNAL_POINTER + "\n")
        return
    before, section, after = parts
    body = entries_of(section)
    if jo.is_file():
        existing = jo.read_text(encoding="utf-8").rstrip("\n")
        write(jo, existing + "\n" + body + "\n")
    else:
        write(jo, JOURNAL_HEADER + body + "\n")
    new = before.rstrip("\n") + "\n\n" + JOURNAL_POINTER + "\n" + (after if after.strip() else "")
    write(ho, new.rstrip("\n") + "\n")
    n = len([l for l in body.split("\n") if l.lstrip().startswith("-")])
    log(f"✅ 2. HANDOFF.md : § Journal ({n} entrées, {len(section)} chars) → HANDOFF-journal.md + pointeur")


# ── Étape 3 : Gotchas code-map ──────────────────────────────────────────────────────────────
GOTCHAS_INTRO = """# Gotchas — pièges non évidents (injectés à la demande)

> **Non auto-chargé** (budget contexte v1.4). Le hook `pretooluse-inject-codemap.py` injecte,
> à l'édition d'un fichier de code, UNIQUEMENT les entrées qui **le ciblent** — une fois
> par session et par fichier. Une entrée cible un fichier en citant en backticks un chemin, un
> nom de fichier ou un dossier : `` `src/sync/notion.py` ``, `` `notion.py` ``, `` `src/sync/` ``.
> Une entrée sans chemin cité n'est injectée que sous un heading « Globaux » (rare et court).

"""
GOTCHAS_POINTER = """## Gotchas → `code-map-gotchas.md`

Les pièges non évidents vivent dans [code-map-gotchas.md](code-map-gotchas.md) (**non auto-chargé**) :
le hook PreToolUse n'injecte que ceux qui citent le fichier en cours d'édition. Ici ne restent que
la vue macro, le couplage et l'intention — ce fichier est auto-chargé à chaque session : < 3k tokens."""


def _has_path(entry: str) -> bool:
    """Même critère que le hook PreToolUse : un token en backticks qui ressemble à un chemin/fichier."""
    toks = re.findall(r"`([^`\n]+)`", entry)
    return any(("/" in t or "." in t) and " " not in t.strip() for t in toks)


def write_gotchas(gf: Path, text: str, origin: str) -> None:
    """Écrit des gotchas migrés dans code-map-gotchas.md en les RANGEANT : une entrée sans chemin
    cité (piège transversal, injecté à CHAQUE édition par le hook < 1.4) va sous un heading
    « Globaux » — sinon le hook ≥ 1.4 ne l'injecterait plus jamais (v1.5.0) ; les autres sous
    « Par zone »."""
    entries = split_entries(text)
    rest = text
    for e in entries:
        rest = rest.replace(e, "", 1)
    rest = re.sub(r"\n{3,}", "\n\n", rest).strip("\n")
    glob = [e for e in entries if not _has_path(e)]
    zone = [e for e in entries if _has_path(e)] + ([rest] if rest.strip() else [])
    if gf.is_file():
        out = gf.read_text(encoding="utf-8").rstrip("\n")
        if glob:
            out += f"\n\n## Globaux — migrés depuis {origin}\n\n" + "\n".join(glob)
        if zone:
            out += f"\n\n## Migrés depuis {origin}\n\n" + "\n".join(zone)
        write(gf, out + "\n")
    else:
        write(gf, GOTCHAS_INTRO + "## Globaux (injectés pour TOUTE édition de code — max 5 lignes)\n\n"
              + ("\n".join(glob) + "\n\n" if glob else "") + "## Par zone\n\n" + "\n".join(zone) + "\n")


def step_codemap_gotchas(root: Path) -> None:
    """Déplace TOUTES les sections `## Gotchas…` (hors pointeur) de code-map.md vers
    code-map-gotchas.md — un projet a pu en empiler plusieurs (v1.5.0 : avant, seule la 1re
    était migrée, les suivantes restaient auto-chargées)."""
    cm = root / ".claude" / "docs" / "code-map.md"
    gf = root / ".claude" / "docs" / "code-map-gotchas.md"
    if not cm.is_file():
        log("⏭ 3. code-map.md absent")
        return
    text = cm.read_text(encoding="utf-8")
    bodies, moved_chars = [], 0
    while True:
        parts = split_section(text, "Gotchas", skip_prefix="## Gotchas →")
        if parts is None:
            break
        before, section, after = parts
        moved_chars += len(section)
        body = entries_of(section)
        if body.strip():
            bodies.append(body)
        pointer = "" if "## Gotchas →" in text else GOTCHAS_POINTER + "\n\n"
        text = (before.rstrip("\n") + "\n\n" + pointer + after.lstrip("\n")).rstrip("\n") + "\n"
    # Puces empilées SOUS le pointeur « ## Gotchas → … » (skills v1.4.x qui écrivaient encore dans
    # code-map.md) : la prose du pointeur reste, les puces partent dans code-map-gotchas.md.
    ptr = split_section(text, "Gotchas →")
    if ptr is not None:
        before, section, after = ptr
        head, _, pbody = section.partition("\n")
        bullets = split_entries(pbody)
        if bullets:
            moved_chars += sum(len(b) for b in bullets)
            bodies.append("\n".join(bullets))
            for b in bullets:
                pbody = pbody.replace(b + "\n", "", 1) if (b + "\n") in pbody else pbody.replace(b, "", 1)
            pbody = re.sub(r"\n{3,}", "\n\n", pbody).strip("\n")
            text = (before.rstrip("\n") + "\n\n" + head + "\n\n" + pbody + "\n\n" + after.lstrip("\n")).rstrip("\n") + "\n"
    if not moved_chars:
        log("⏭ 3. code-map.md : gotchas déjà externalisés")
        step_codemap_update_section(root)  # 3b indépendante : des ⚠️ ont pu s'empiler depuis
        return
    write_gotchas(gf, "\n\n".join(bodies), "code-map.md")
    write(cm, text)
    log(f"✅ 3. code-map.md : § Gotchas ({moved_chars} chars) → code-map-gotchas.md + pointeur")
    step_codemap_update_section(root)


def split_entries(body: str):
    """Bullets (+ lignes de continuation indentées) d'un corps de section."""
    entries, cur = [], []
    for line in body.split("\n"):
        if re.match(r"\s*[-*]\s", line):
            if cur:
                entries.append("\n".join(cur))
            cur = [line.rstrip()]
        elif cur and line.startswith((" ", "\t")) and line.strip():
            cur.append(line.rstrip())
        elif cur:
            entries.append("\n".join(cur)); cur = []
    if cur:
        entries.append("\n".join(cur))
    return entries


def step_codemap_update_section(root: Path) -> None:
    """§ « Quand mettre à jour ce fichier » (consigne de 4 lignes dans le template) : vécu 2026-09-08,
    18,9k chars sur un projet — des gotchas `⚠️` appendés au mauvais endroit, auto-chargés à chaque
    session. Les entrées `⚠️` ou > 300 chars partent dans code-map-gotchas.md ; la consigne reste."""
    cm = root / ".claude" / "docs" / "code-map.md"
    gf = root / ".claude" / "docs" / "code-map-gotchas.md"
    text = cm.read_text(encoding="utf-8")
    parts = split_section(text, "Quand mettre à jour")
    if parts is None:
        return
    before, section, after = parts
    head, _, body = section.partition("\n")
    entries = split_entries(body)
    moved = [e for e in entries if "⚠️" in e.split("\n")[0] or len(e) > 300]
    if not moved:
        return
    # On RETIRE les entrées déplacées du corps d'origine — tout le reste (prose, blockquote entre
    # deux puces, consignes) est conservé tel quel (v1.5.0 : la reconstruction « puces gardées +
    # queue » perdait le texte non-puce situé avant/entre les entrées).
    new_body = body
    for e in moved:
        new_body = new_body.replace(e + "\n", "", 1) if (e + "\n") in new_body else new_body.replace(e, "", 1)
    new_body = re.sub(r"\n{3,}", "\n\n", new_body).strip("\n")
    write_gotchas(gf, "\n".join(moved), "« Quand mettre à jour ce fichier »")
    new_section = head + "\n\n" + new_body
    write(cm, (before.rstrip("\n") + "\n\n" + new_section.rstrip("\n") + "\n\n" + after.lstrip("\n")).rstrip("\n") + "\n")
    log(f"✅ 3b. code-map.md : {len(moved)} entrée(s) ⚠️/longues de « Quand mettre à jour » → code-map-gotchas.md ({sum(len(e) for e in moved)} chars)")


# ── Étape 4 : ROADMAP ───────────────────────────────────────────────────────────────────────
def step_roadmap(root: Path) -> None:
    p = root / "CLAUDE.md"
    if not p.is_file():
        log("⏭ 4. CLAUDE.md absent")
        return
    text = p.read_text(encoding="utf-8")
    if "@.claude/docs/ROADMAP.md" not in text:
        log("⏭ 4. CLAUDE.md : ROADMAP déjà en lien simple")
        return
    text = text.replace("@.claude/docs/ROADMAP.md", "[ROADMAP.md](.claude/docs/ROADMAP.md) (dashboard — lu à la demande par /spec, /conception, /feature-done, /doc-health)")
    text = re.sub(r"seuls les 3 docs d'état vivant", "seuls les 2 docs d'état vivant", text)
    write(p, text)
    log("✅ 4. CLAUDE.md : @ROADMAP → lien simple")


# ── Étape 5 : fichiers v1.4 depuis le template ─────────────────────────────────────────────
# (chemin dans le projet, chemin dans le template) — v1.5.0 : la rule d'équipe vit dans le plugin
# agent-teams (copiée par son activation) ; mise à jour ici seulement si le projet l'a déjà.
TEMPLATE_FILES = [
    (".claude/rules/agent-teams.md", "plugins/agent-teams/skills/team/agent-teams-rule.md"),
    (".claude/hooks/pretooluse-inject-codemap.py", ".claude/hooks/pretooluse-inject-codemap.py"),
    (".claude/hooks/sessionstart-inject-handoff.py", ".claude/hooks/sessionstart-inject-handoff.py"),
    (".claude/hooks/snapshot_common.py", ".claude/hooks/snapshot_common.py"),
    (".claude/skills/doc-health/scripts/context-budget.py", ".claude/skills/doc-health/scripts/context-budget.py"),
]


def step_template_files(root: Path, template: Path) -> None:
    for rel, src_rel in TEMPLATE_FILES:
        src, dst = template / src_rel, root / rel
        if not src.is_file():
            log(f"⏭ 5. {rel} : absent du template ({template})")
            continue
        if rel.endswith("context-budget.py"):
            if not (root / ".claude" / "skills" / "doc-health").is_dir():
                log(f"⏭ 5. {rel} : /doc-health absent du projet (profil sans audit)")
                continue
        elif not dst.is_file():
            log(f"⏭ 5. {rel} : absent du projet (profil l'a retiré) — pas de greffe")
            continue
        if dst.is_file() and dst.read_bytes() == src.read_bytes():
            log(f"⏭ 5. {rel} : déjà à jour")
            continue
        if not DRY:
            if rel.endswith("agent-teams.md") and dst.is_file():
                bak = root / ".claude" / ".cache" / "agent-teams.md.pre-1.4"
                bak.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, bak)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        log(f"✅ 5. {rel} : copié depuis le template" + (" (ancienne rule → .claude/.cache/agent-teams.md.pre-1.4)" if rel.endswith("agent-teams.md") else ""))


def main() -> int:
    global DRY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-template-files", action="store_true")
    ap.add_argument("--template", default=None, help="racine du template (défaut : celle de ce script)")
    a = ap.parse_args()
    DRY = a.dry_run
    root = Path(a.root).resolve()
    if not (root / ".claude").is_dir():
        print(f"❌ {root} : pas de .claude/ (pas un projet du template)", file=sys.stderr)
        return 2
    template = Path(a.template).resolve() if a.template else Path(__file__).resolve().parents[4]
    print(f"🪶 slim-context v1.4 — {root}" + (" (dry-run)" if DRY else ""))
    step_unimport_scoped_rules(root)
    step_handoff_journal(root)
    step_codemap_gotchas(root)
    step_roadmap(root)
    if a.no_template_files:
        log("⏭ 5. fichiers template ignorés (--no-template-files)")
    else:
        step_template_files(root, template)
    print("\n→ Vérifie : python3 .claude/skills/doc-health/scripts/context-budget.py --root " + str(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
