"""Le schéma anglais (plan 002, D8) : les fichiers versionnés tirés de la table de correspondance
(python -m banc anglais), et la traduction des requêtes de questions/ pour la preuve de la bascule
(python -m banc traduire --vers D). banc ne joint jamais la base : scripts/charger.sh --schema et
scripts/questions.sh --dossier D jouent ces fichiers.
"""

import re
import sys
import textwrap
from pathlib import Path

from banc import correspondance, traduction
from banc.correspondance import Correspondance

RACINE = Path(__file__).resolve().parents[3]
QUESTIONS = RACINE / "questions"
QUESTIONS_SH = RACINE / "scripts" / "questions.sh"
CONTRAINTES_FR = RACINE / "cypher" / "00-contraintes.cypher"
CONTRAINTES_EN = correspondance.DOSSIER / "contraintes.cypher"
PRODUIT = "uv run --directory banc python -m banc anglais"


def contraintes(table: Correspondance) -> str:
    """Contraintes et index en anglais : 00-contraintes.cypher traduit, sans ses commentaires."""
    entete = (
        "// Contraintes et index du schéma anglais (spec 002, plan D8) : 00-contraintes.cypher\n"
        "// traduit par correspondance.toml, produit par\n"
        f"// `{PRODUIT}` : ne pas l'éditer.\n"
        "// scripts/charger.sh --schema en le joue après le renommage des données ; --schema fr\n"
        "// rejoue cypher/00-contraintes.cypher.\n"
    )
    francais = traduction.sans_commentaires(CONTRAINTES_FR.read_text())
    return entete + "\n" + traduction.traduire(francais, table, "en")


def produits(table: Correspondance) -> dict[Path, str]:
    """Les fichiers tirés de la table, avec leur contenu attendu."""
    return {
        correspondance.CARTE: correspondance.carte(table),
        CONTRAINTES_EN: contraintes(table),
    }


def commande() -> int:
    """Écrit les fichiers tirés de la table ; dit lesquels ont changé."""
    table = correspondance.charger()
    for chemin, texte in produits(table).items():
        avant = chemin.read_text() if chemin.exists() else None
        if avant != texte:
            chemin.write_text(texte)
        etat = "inchangé" if avant == texte else "écrit"
        sys.stdout.write(f"✓ {chemin.relative_to(RACINE)} : {etat}\n")
    return 0


# --- Traduction des requêtes de questions/ (T6.2) ------------------------------------------------

# Les deux recherches de l'index plein texte que scripts/questions.sh --exemples joue après les
# exemples de la fiche, sous le nom de fichier qu'il attend avec --dossier (D/exemples/…).
RECHERCHES = {"dracofeu": "DRACOFEU", "electrik": "ELECTRIK"}


def exemples_de_la_fiche(fiche: str) -> list[str]:
    """Les blocs ```cypher de la fiche, dans l'ordre, comme scripts/questions.sh les lit."""
    return re.findall(r"^```cypher\n(.*?)^```$", fiche, re.MULTILINE | re.DOTALL)


def recherche(variable: str, script: str | None = None) -> str:
    """Une recherche de scripts/questions.sh (readonly DRACOFEU="…") : la source unique de la
    version française."""
    texte = QUESTIONS_SH.read_text() if script is None else script
    trouve = re.search(rf'^readonly {variable}="([^"]*)"$', texte, re.MULTILINE)
    if trouve is None:
        raise ValueError(f"{variable} introuvable dans scripts/questions.sh")
    return trouve.group(1) + "\n"


def corpus() -> dict[str, str]:
    """Les textes Cypher français à traduire, par chemin dans le dossier de la traduction : les 27
    requêtes et la liste des espèces, les vérifications de la fiche, ses exemples, puis les deux
    recherches de questions.sh (contrat de --dossier, plan D8)."""
    textes = {f.name: f.read_text() for f in sorted(QUESTIONS.glob("q[0-9][0-9].cypher"))}
    for nom in ("especes.cypher", "fiche.cypher"):
        textes[nom] = (QUESTIONS / nom).read_text()
    exemples = exemples_de_la_fiche((QUESTIONS / "fiche-schema.md").read_text())
    for rang, exemple in enumerate(exemples, start=1):
        textes[f"exemples/exemple-{rang}.cypher"] = exemple
    for nom, variable in RECHERCHES.items():
        textes[f"exemples/{nom}.cypher"] = recherche(variable)
    return textes


BALAYAGE = """
// Balayage (spec 002, D8), ajouté par banc traduire : labels, types et clés que porte le graphe
// hors du schéma anglais de la table. Attendu : aucun, donc plus aucun identifiant français.
CALL () {{ MATCH (n) UNWIND labels(n) AS x RETURN collect(DISTINCT x) AS labels }}
CALL () {{ MATCH ()-[r]->() RETURN collect(DISTINCT type(r)) AS types }}
CALL () {{ MATCH (n) UNWIND keys(n) AS x RETURN collect(DISTINCT x) AS clesNoeuds }}
CALL () {{ MATCH ()-[r]->() UNWIND keys(r) AS x RETURN collect(DISTINCT x) AS clesRelations }}
WITH COLLECT {{
  UNWIND labels + types + clesNoeuds + clesRelations AS x
  WITH DISTINCT x
  WHERE NOT x IN [
{liste}
  ]
  RETURN x ORDER BY x
}} AS hors
RETURN 'balayage : labels, types et clés hors du schéma anglais|aucun|'
  + CASE WHEN hors = [] THEN 'aucun'
    ELSE reduce(s = '', x IN hors | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) END AS ligne;
"""


def balayage(table: Correspondance) -> str:
    """La requête de balayage, ajoutée à fiche.cypher traduit : les labels, types et clés que porte
    le graphe hors du schéma anglais de la table ; réponse attendue : aucun."""
    genres = ("labels", "relations", "proprietes")
    anglais = {n for g in genres for n in table.sens("en")[g].values()}
    anglais |= {n for g in genres for n in table.communs[g]}
    liste = ", ".join(f"'{nom}'" for nom in sorted(anglais))
    return BALAYAGE.format(
        liste=textwrap.fill(liste, 96, initial_indent="    ", subsequent_indent="    ")
    )


def traductions(table: Correspondance) -> dict[str, str]:
    """Le corpus traduit vers l'anglais, chaque fichier sous un en-tête qui dit d'où il vient ;
    fiche.cypher suivi du balayage."""
    resultat = {}
    for chemin, texte in corpus().items():
        entete = f"// Traduit vers le schéma anglais par banc traduire (D8) : {_source(chemin)}.\n"
        traduit = entete + traduction.traduire(texte, table, "en")
        if chemin == "fiche.cypher":
            traduit += balayage(table)
        resultat[chemin] = traduit
    return resultat


def _source(chemin: str) -> str:
    """D'où vient un fichier du corpus : questions/, la fiche (ses exemples) ou questions.sh."""
    nom = Path(chemin).stem
    if nom in RECHERCHES:
        return f"scripts/questions.sh ({RECHERCHES[nom]})"
    return "questions/fiche-schema.md" if chemin.startswith("exemples/") else f"questions/{chemin}"


def commande_traduire(dossier: Path) -> int:
    """Écrit le corpus traduit dans le dossier (logs/anglais pour T10.1) : les fichiers qu'y lit
    scripts/questions.sh --dossier."""
    table = correspondance.charger()
    textes = traductions(table)
    for chemin, texte in textes.items():
        cible = dossier / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(texte)
    sys.stdout.write(f"✓ {len(textes)} fichiers traduits dans {dossier}\n")
    return 0
