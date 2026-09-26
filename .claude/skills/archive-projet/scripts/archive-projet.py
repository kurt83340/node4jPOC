#!/usr/bin/env python3
"""archive-projet.py — mécanique déterministe du skill /archive-projet.

Sous-commandes :
  archive --reason "<r>" [--dest <dir>] [--root <dir>] [--dry-run]
  restore [--dest <dir>] [--root <dir>] [--dry-run]
  status  [--root <dir>]

`archive` : pré-flight (projet template ? déjà archivé ? worktrees actifs ? destination
libre ?), écrit le marqueur `.claude/archived` (date, raison, chemins aller/retour), insère
la bannière en tête du CLAUDE.md racine (entre marqueurs HTML — retirable au restore), scanne
les références au chemin absolu (repo + crontab + ~/.claude.json, RAPPORT SEUL — jamais de
correction silencieuse), localise l'auto-memory (~/.claude/projects/<slug>) et imprime la
COMMANDE FINALE (mkdir + mv projet + mv mémoire) à lancer APRÈS fermeture de la session.

⚠️ Le script ne déplace JAMAIS le projet lui-même : on ne déplace pas le dossier dans lequel
la session Claude Code tourne (cwd, hooks ${CLAUDE_PROJECT_DIR}, approbations keyées chemin).

`restore` : inverse — retire bannière + marqueur, imprime la commande de move retour.
`status` : affiche le marqueur ou « non archivé ».

Home surchargeable via $ARCHIVE_PROJET_HOME (tests). Stdlib pur. Exit 0 = OK, 2 = bloqueur.
"""
import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

MARKER_REL = Path(".claude") / "archived"
BANNER_START = "<!-- archive-projet:start -->"
BANNER_END = "<!-- archive-projet:end -->"
SKIP_DIRS = {".git", ".cache", "node_modules", "__pycache__", ".venv", "venv"}


def home() -> Path:
    return Path(os.environ.get("ARCHIVE_PROJET_HOME", str(Path.home())))


def slug(path: Path) -> str:
    """Slug auto-memory de Claude Code : tout caractère non alphanumérique → '-'.
    Ex. /home/x/projets/mon_projet → -home-x-projets-mon-projet (vérifié empiriquement —
    si le format drifte, memory_dir() ne matche plus et la migration est simplement sautée
    avec un message, jamais fausse)."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def memory_dir(path: Path) -> Path:
    return home() / ".claude" / "projects" / slug(path)


def sh(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def parse_marker(root: Path):
    p = root / MARKER_REL
    if not p.is_file():
        return None
    d = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.partition(":")
        if sep:
            d[k.strip()] = v.strip()
    return d


def banner_text(reason: str, day: str) -> str:
    return "\n".join([
        BANNER_START,
        f"> ⚠️ **PROJET ARCHIVÉ** ({day}) — raison : {reason}.",
        "> Lecture seule par défaut — pour reprendre : `/archive-projet restore`.",
        BANNER_END,
        "",
        "",
    ])


def strip_banner_text(text: str) -> str:
    pat = re.compile(re.escape(BANNER_START) + r".*?" + re.escape(BANNER_END) + r"\n*", re.S)
    return pat.sub("", text)


def insert_banner(root: Path, reason: str, day: str, dry: bool) -> None:
    cm = root / "CLAUDE.md"
    prefix = "DRY-RUN : " if dry else ""
    if not cm.is_file():
        print("⚠️  CLAUDE.md racine absent — bannière sautée (le marqueur .claude/archived suffit)")
        return
    if not dry:
        text = strip_banner_text(cm.read_text(encoding="utf-8"))
        cm.write_text(banner_text(reason, day) + text, encoding="utf-8")
    print(f"{prefix}bannière insérée en tête de CLAUDE.md")


def scan_refs(root: Path):
    """Occurrences du chemin absolu du projet dans ses propres fichiers (rapport)."""
    needle = str(root)
    hits = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(root)
        if rel == MARKER_REL or any(part in SKIP_DIRS for part in rel.parts):
            continue
        try:
            n = p.read_text(encoding="utf-8", errors="ignore").count(needle)
        except OSError:
            continue
        if n:
            hits.append((str(rel), n))
    return hits


def scan_external(root: Path):
    """Référents externes détectables (rapport seul, jamais de correction)."""
    needle = str(root)
    out = []
    r = sh(["crontab", "-l"])
    if r.returncode == 0 and needle in r.stdout:
        out.append(f"crontab : {r.stdout.count(needle)} occurrence(s) — à repointer AVANT le move")
    cj = home() / ".claude.json"
    if cj.is_file():
        try:
            n = cj.read_text(encoding="utf-8", errors="ignore").count(needle)
        except OSError:
            n = 0
        if n:
            out.append(f"~/.claude.json : {n} occurrence(s) (approbations/historique keyés chemin "
                       "— NE PAS éditer : re-prompt bénin après le move)")
    return out


def worktree_count(root: Path) -> int:
    r = sh(["git", "worktree", "list", "--porcelain"], cwd=root)
    if r.returncode != 0:
        return 0  # pas un repo git
    return sum(1 for line in r.stdout.splitlines() if line.startswith("worktree "))


def final_cmd(src: Path, dst: Path):
    parts = [f"mkdir -p '{dst.parent}'", f"mv '{src}' '{dst}'"]
    mem_src, mem_dst = memory_dir(src), memory_dir(dst)
    if mem_src.is_dir():
        parts.append(f"mv '{mem_src}' '{mem_dst}'")
        note = f"auto-memory détectée ({mem_src}) — migrée par la commande finale"
    else:
        note = f"aucune auto-memory détectée (slug {mem_src.name}) — rien à migrer"
    return " && ".join(parts), note


def print_final(cmd: str) -> None:
    print("\n=== COMMANDE FINALE — à lancer APRÈS fermeture de cette session, "
          "depuis un autre terminal ===")
    print(cmd)


def report_scans(root: Path) -> None:
    hits = scan_refs(root)
    if hits:
        print(f"\n📎 Références INTERNES au chemin absolu ({len(hits)} fichier(s)) — "
              "elles voyagent avec le move mais resteront fausses si absolues :")
        for rel, n in hits:
            print(f"   - {rel} ({n})")
    else:
        print("\n📎 Aucune référence interne au chemin absolu du projet.")
    ext = scan_external(root)
    if ext:
        print("🔗 Référents EXTERNES détectés :")
        for e in ext:
            print(f"   - {e}")
    else:
        print("🔗 Aucun référent externe détecté (crontab, ~/.claude.json). Reste à vérifier "
              "à la main : CI, workflows n8n appelant un chemin local du projet.")


def cmd_archive(a) -> int:
    root = Path(a.root).resolve()
    dry = a.dry_run
    prefix = "DRY-RUN : " if dry else ""
    if not (root / ".claude").is_dir():
        print(f"❌ {root} : pas un projet template (.claude/ absent) — préciser --root.")
        return 2
    if parse_marker(root):
        print("❌ Projet déjà archivé (.claude/archived présent) — voir status / restore.")
        return 2
    wt = worktree_count(root)
    if wt > 1:
        print(f"❌ {wt - 1} worktree(s) actif(s) — merger/retirer avant d'archiver "
              "(git worktree list).")
        return 2
    dest = Path(a.dest).resolve() if a.dest else root.parent / "_archives" / root.name
    if dest.exists():
        print(f"❌ Destination déjà occupée : {dest}")
        return 2
    r = sh(["git", "status", "--porcelain"], cwd=root)
    if r.returncode == 0 and r.stdout.strip():
        print("⚠️  Modifications non committées — le commit final du skill doit les embarquer.")
    day = date.today().isoformat()
    print(f"Projet      : {root}")
    print(f"Destination : {dest}")
    print(f"Raison      : {a.reason}")
    if not dry:
        marker = root / MARKER_REL
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            f"archived: {day}\nreason: {a.reason}\n"
            f"original-path: {root}\narchived-path: {dest}\n",
            encoding="utf-8")
    print(f"{prefix}marqueur .claude/archived écrit")
    insert_banner(root, a.reason, day, dry)
    report_scans(root)
    cmd, note = final_cmd(root, dest)
    print(f"🧠 {note}")
    print_final(cmd)
    return 0


def cmd_restore(a) -> int:
    root = Path(a.root).resolve()
    dry = a.dry_run
    prefix = "DRY-RUN : " if dry else ""
    m = parse_marker(root)
    if not m:
        print("❌ Pas de marqueur .claude/archived — projet non archivé.")
        return 2
    back = Path(a.dest).resolve() if a.dest else Path(m.get("original-path", ""))
    if str(back) in ("", "."):
        print("❌ original-path illisible dans le marqueur — passer --dest.")
        return 2
    in_place = back == root  # archivé mais jamais déplacé (ou déjà revenu) : pas de move
    if not in_place and back.exists():
        print(f"❌ Destination de retour déjà occupée : {back}")
        return 2
    cm = root / "CLAUDE.md"
    if cm.is_file():
        text = cm.read_text(encoding="utf-8")
        stripped = strip_banner_text(text)
        if stripped != text:
            if not dry:
                cm.write_text(stripped, encoding="utf-8")
            print(f"{prefix}bannière retirée de CLAUDE.md")
        else:
            print("pas de bannière à retirer dans CLAUDE.md")
    if not dry:
        (root / MARKER_REL).unlink()
    print(f"{prefix}marqueur .claude/archived retiré")
    if in_place:
        print("✔ projet déjà à l'emplacement d'origine — aucun move nécessaire")
        return 0
    cmd, note = final_cmd(root, back)
    print(f"🧠 {note}")
    print_final(cmd)
    return 0


def cmd_status(a) -> int:
    root = Path(a.root).resolve()
    m = parse_marker(root)
    if not m:
        print("non archivé")
        return 0
    for k in ("archived", "reason", "original-path", "archived-path"):
        print(f"{k}: {m.get(k, '?')}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("archive", help="marquer archivé + préparer le move")
    p.add_argument("--reason", required=True)
    p.add_argument("--dest")
    p.add_argument("--root", default=".")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("restore", help="retirer le marquage + préparer le move retour")
    p.add_argument("--dest")
    p.add_argument("--root", default=".")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("status", help="afficher l'état d'archivage")
    p.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    return {"archive": cmd_archive, "restore": cmd_restore, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
