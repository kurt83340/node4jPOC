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
from banc.correspondance import Correspondance, CorrespondanceError
from banc.traduction import TraductionError

RACINE = Path(__file__).resolve().parents[3]
QUESTIONS = RACINE / "questions"
QUESTIONS_SH = RACINE / "scripts" / "questions.sh"
CONTRAINTES_FR = RACINE / "cypher" / "00-contraintes.cypher"
FICHE_FR = QUESTIONS / "fiche-schema.md"
FICHE_EN = QUESTIONS / "fiche-schema.en.md"
CONTRAINTES_EN = correspondance.DOSSIER / "contraintes.cypher"
PRODUIT = "uv run --directory banc python -m banc anglais"
# Le corpus traduit (T10.1), où scripts/questions.sh --dossier le lit, et où banc lancer prend la
# traduction de q02.cypher pour le contrôle de Q2 d'une campagne anglaise (T10.0).
TRADUCTION = RACINE / "logs" / "anglais"
ENTETE = "// Traduit vers le schéma anglais par banc traduire (D8) : "


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


def fiche(table: Correspondance) -> str:
    """La fiche de schéma anglaise : la fiche française, identifiants traduits, sans rien d'autre
    (elle va telle quelle dans le prompt des passes anglaises : pas d'en-tête)."""
    return traduction.traduire_fiche(FICHE_FR.read_text(), table, "en")


def produits(table: Correspondance) -> dict[Path, str]:
    """Les fichiers tirés de la table, avec leur contenu attendu."""
    return {
        correspondance.CARTE: correspondance.carte(table),
        CONTRAINTES_EN: contraintes(table),
        FICHE_EN: fiche(table),
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
    exemples = exemples_de_la_fiche(FICHE_FR.read_text())
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
        traduit = f"{ENTETE}{_source(chemin)}.\n" + traduction.traduire(texte, table, "en")
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
    scripts/questions.sh --dossier. Un chemin relatif part de la racine du dépôt, quel que soit le
    dossier courant (uv run --directory banc en change). Le dossier est vidé avant, pour qu'aucune
    traduction périmée n'y reste : il ne doit contenir que des fichiers d'une traduction
    précédente, et aucun lien symbolique (un lien vers un dossier ferait écrire ailleurs) ; sinon
    rien n'est effacé ni écrit (code 2). La traduction se calcule avant d'effacer quoi que ce
    soit."""
    cible = dossier if dossier.is_absolute() else RACINE / dossier
    try:
        textes = traductions(correspondance.charger())
    except (CorrespondanceError, TraductionError, ValueError, OSError) as erreur:
        sys.stderr.write(f"banc traduire : traduction impossible, rien n'est effacé : {erreur}\n")
        return 2
    if cible.is_symlink() or (cible.exists() and not cible.is_dir()):
        sys.stderr.write(f"banc traduire : {cible} n'est pas un dossier (ou c'est un lien)\n")
        return 2
    anciens: list[Path] = []
    # Arrêt au premier élément refusé, avant d'effacer quoi que ce soit ; un lien se refuse avant
    # de savoir s'il mène à un dossier (rglob n'y descend pas).
    for chemin in cible.rglob("*") if cible.is_dir() else ():
        if chemin.is_dir() and not chemin.is_symlink():
            continue
        if chemin.is_symlink() or not _traduit(chemin):
            sys.stderr.write(
                f"banc traduire : {cible} contient {chemin.relative_to(cible)}, qui n'est pas "
                "une traduction de banc traduire : rien n'est effacé ; choisir un dossier vide\n"
            )
            return 2
        anciens.append(chemin)
    for chemin in anciens:
        chemin.unlink()
    for nom, texte in textes.items():
        fichier = cible / nom
        fichier.parent.mkdir(parents=True, exist_ok=True)
        # « x » : jamais un fichier écrasé, le dossier vient d'être vidé.
        with fichier.open("x", encoding="utf-8") as flux:
            flux.write(texte)
    sys.stdout.write(f"✓ {len(textes)} fichiers traduits dans {cible}\n")
    return 0


def _traduit(fichier: Path) -> bool:
    """Le fichier vient de banc traduire : un fichier ordinaire, sous son en-tête."""
    if not fichier.is_file():
        return False
    try:
        with fichier.open(encoding="utf-8") as flux:
            return flux.readline().startswith(ENTETE)
    except UnicodeDecodeError:
        return False


def ecarts_de_traduction(dossier: Path = TRADUCTION) -> list[str]:
    """Ce qui sépare le dossier de la traduction du corpus d'aujourd'hui : fichiers absents,
    différents, ou en trop ; vide si le dossier est à jour (banc lancer, schéma anglais)."""
    attendus = traductions(correspondance.charger())
    if not dossier.is_dir():
        return ["dossier absent"]
    presents = {str(f.relative_to(dossier)) for f in dossier.rglob("*") if not f.is_dir()}
    ecarts = [f"{chemin} absent" for chemin in sorted(set(attendus) - presents)]
    ecarts += [
        f"{chemin} périmé"
        for chemin in sorted(set(attendus) & presents)
        if (dossier / chemin).read_text(encoding="utf-8") != attendus[chemin]
    ]
    ecarts += [f"{chemin} en trop" for chemin in sorted(presents - set(attendus))]
    return ecarts
