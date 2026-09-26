#!/usr/bin/env python3
"""
render.py — Substitue les placeholders {{...}} dans tous les fichiers .md du template.

Convention :
  - CORE placeholders : UPPER_SNAKE_CASE → substituables auto via vars.json
    (ex: {{PROJECT_NAME}}, {{CLIENT_NAME}}, {{NOM_DECIDEUR}})
  - CONTENT placeholders : minuscule libre → à remplir manuellement au fil de l'eau
    (ex: {{situation actuelle, douleurs}}, {{seuil}})

Usage:
    python3 render.py --vars vars.json
    python3 render.py --list-placeholders          # tous
    python3 render.py --list-placeholders --core   # seulement CORE
    python3 render.py --check                      # vérifie que tous les CORE sont substitués
"""

import argparse
import json
import re
import sys
from pathlib import Path

PATTERNS = ["**/*.md", "CLAUDE.md", "README.md", ".env.example"]
EXCLUDE = [
    "EXAMPLES/",
    ".git/",
    "node_modules/",
    # Skills/agents = du code (SKILL.md, *.md) qui DOCUMENTE des placeholders
    # via exemples — ne pas substituer dedans
    ".claude/skills/",
    ".claude/agents/",
    # Meta-docs du template (parlent du système, contiennent exemples)
    "STRUCTURE.md",
    "USAGE.md",
    # test/ contient des rapports qui citent {{UPPER_SNAKE}} en exemple (pas de vraies vars)
    "test/",
    # Plugins (source du marketplace) : leurs .md regorgent d'expressions n8n {{ }} —
    # du CONTENU de référence, jamais des placeholders à substituer
    "plugins/",
    ".claude-plugin/",
]

# Une placeholder est CORE si son nom est COMPOUND_UPPER_SNAKE :
#   - Au moins 2 lettres majuscules au début (élimine {{X}}, {{URL}})
#   - Au moins 1 underscore (élimine {{ADR}}, {{XXXX}})
#   - Au moins 2 caractères après l'underscore
# Exemples CORE : {{PROJECT_NAME}}, {{CLIENT_NAME}}, {{NOM_DECIDEUR}}, {{COMMANDE_INSTALL}}
# Exemples CONTENT : {{X}}, {{ADR}}, {{URL}}, {{seuil}}, {{situation actuelle}}
CORE_REGEX = re.compile(r"^[A-Z]{2,}_[A-Z][A-Z0-9_]+$")


def is_core(placeholder: str) -> bool:
    """Détermine si un placeholder est CORE (COMPOUND_UPPER_SNAKE) ou CONTENT."""
    return bool(CORE_REGEX.match(placeholder.strip()))


def is_excluded(rel_path: str) -> bool:
    """Motifs d'EXCLUDE testés sur le chemin RELATIF à la racine, ancrés sur des
    frontières de segments — jamais en substring sur le chemin absolu :

    - sinon un projet situé sous un dossier parent nommé comme un motif (ex.
      `.../test/projetA/` vs EXCLUDE "test/") verrait TOUS ses fichiers exclus
      → « 0 fichiers à scanner » → init silencieusement à vide (bug 2026-07-05) ;
    - l'ancrage `/` évite les faux positifs de substring (`latest/` ≠ `test/`).

    "dir/"  → exclut tout fichier sous un segment de ce nom (racine ou milieu).
    "f.md"  → exclut ce nom de fichier exact (racine ou sous-dossier).
    """
    haystack = "/" + rel_path
    for ex in EXCLUDE:
        if ex.endswith("/"):
            if "/" + ex in haystack:
                return True
        elif haystack.endswith("/" + ex):
            return True
    return False


def find_files(root: Path) -> list[Path]:
    files = set()
    for pattern in PATTERNS:
        for f in root.glob(pattern):
            if f.is_file() and not is_excluded(f.relative_to(root).as_posix()):
                files.add(f)
    return sorted(files)


def find_placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{\{([^}]+)\}\}", text))


def substitute(text: str, variables: dict[str, str]) -> tuple[str, int]:
    count = 0
    for key, value in variables.items():
        pattern = "{{" + key + "}}"
        new_text = text.replace(pattern, value)
        count += text.count(pattern)
        text = new_text
    return text, count


def main():
    parser = argparse.ArgumentParser(description="Substitue les placeholders du template")
    parser.add_argument("--vars", type=Path, help="Fichier JSON avec les variables CORE")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Racine du projet")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas écrire, juste lister")
    parser.add_argument("--list-placeholders", action="store_true", help="Liste les placeholders")
    parser.add_argument("--core", action="store_true", help="Filtrer sur CORE uniquement (avec --list)")
    parser.add_argument("--check", action="store_true", help="Vérifie qu'aucun CORE ne reste")
    args = parser.parse_args()

    root = args.root.resolve()
    files = find_files(root)
    print(f"📁 {len(files)} fichiers à scanner dans {root}")

    # MODE 1 : --list-placeholders
    if args.list_placeholders:
        all_placeholders = set()
        for f in files:
            try:
                all_placeholders.update(find_placeholders(f.read_text(encoding="utf-8")))
            except Exception as e:
                print(f"⚠️  Skip {f}: {e}")

        core = sorted(p for p in all_placeholders if is_core(p))
        content = sorted(p for p in all_placeholders if not is_core(p))

        if args.core:
            print(f"\n🔑 CORE placeholders ({len(core)}) — substituables auto via vars.json :")
            for ph in core:
                print(f"  - {{{{{ph}}}}}")
        else:
            print(f"\n🔑 CORE ({len(core)}) — auto-substituables :")
            for ph in core:
                print(f"  - {{{{{ph}}}}}")
            print(f"\n📝 CONTENT ({len(content)}) — à remplir manuellement :")
            for ph in content[:20]:
                print(f"  - {{{{{ph}}}}}")
            if len(content) > 20:
                print(f"  ... et {len(content) - 20} autres")
        return 0

    # MODE 2 : --check (uniquement CORE)
    if args.check:
        remaining_core = set()
        for f in files:
            try:
                for ph in find_placeholders(f.read_text(encoding="utf-8")):
                    if is_core(ph):
                        remaining_core.add(ph)
            except Exception:
                pass
        if remaining_core:
            print(f"\n❌ {len(remaining_core)} placeholders CORE non substitués :")
            for ph in sorted(remaining_core):
                print(f"  - {{{{{ph}}}}}")
            return 1
        print("\n✅ Tous les placeholders CORE sont substitués")
        return 0

    # MODE 3 : --vars (substitution)
    if not args.vars:
        print("❌ --vars requis (sauf --list-placeholders ou --check)", file=sys.stderr)
        return 1

    variables = json.loads(args.vars.read_text())
    print(f"📋 {len(variables)} variables à substituer")

    non_core_vars = [k for k in variables if not is_core(k)]
    if non_core_vars:
        print(f"⚠️  {len(non_core_vars)} variables ne suivent pas la convention UPPER_SNAKE :")
        for k in non_core_vars:
            print(f"  - {k} (devrait être MAJUSCULES_SNAKE)")

    total_replacements = 0
    modified_files = 0

    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
            new_text, count = substitute(text, variables)
            if count > 0:
                total_replacements += count
                modified_files += 1
                if args.dry_run:
                    print(f"  [DRY] {f.relative_to(root)} : {count} remplacements")
                else:
                    f.write_text(new_text, encoding="utf-8")
                    print(f"  ✅ {f.relative_to(root)} : {count} remplacements")
        except Exception as e:
            print(f"  ⚠️  {f}: {e}", file=sys.stderr)

    print(f"\n🎉 Total : {total_replacements} remplacements dans {modified_files} fichiers")

    # Check post-substitution : uniquement CORE manquants (CONTENT = normal)
    remaining_core = set()
    remaining_content = 0
    for f in files:
        try:
            for ph in find_placeholders(f.read_text(encoding="utf-8")):
                if is_core(ph):
                    remaining_core.add(ph)
                else:
                    remaining_content += 1
        except Exception:
            pass

    if remaining_core:
        print(f"\n⚠️  {len(remaining_core)} CORE manquants — ajoute au vars.json et relance :")
        for ph in sorted(remaining_core):
            print(f"  - {{{{{ph}}}}}")
    else:
        print("\n✅ Tous les CORE substitués")

    print(f"📝 {remaining_content} CONTENT placeholders à remplir au fil de l'eau (normal)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
