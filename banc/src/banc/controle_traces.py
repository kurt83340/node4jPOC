"""Contrôle des traces d'une campagne (spec 003, T15.1 ; US1 et US4) : banc controle-traces.

Les traces d'une campagne (logs/banc/<campagne>/, banc.mesures) montrent ce qui s'est passé pendant
les questions ; ce contrôle en fait une commande, dont le code retour porte chacun des contrôles :

1. outils : chaque appel est une lecture read-cypher, le seul chemin vers la base (US1) ;
2. écritures : aucune clause d'écriture dans les requêtes (US1), lues jeton par jeton
   (banc.traduction) : un mot dans une chaîne, un commentaire, un nom entre accents graves, une
   propriété, un label ou une clé de map n'en est pas une. Une écriture tentée compte, même refusée
   par read-cypher. Les procédures ne sont pas lues : read-cypher classe chaque requête par son
   EXPLAIN (neo4j-mcp v1.6.0) ;
3. jetons Google : aucun « ya29. », début d'un jeton d'accès OAuth de Google, dans les fichiers
   de la campagne ;
4. vecteurs : aucune suite de SEUIL_VECTEUR nombres ou plus dans les traces (US4) : paramètres,
   résultats (le contexte d'une technique sans outil), messages et réponses, lus sur le texte de
   chaque ligne, une ligne coupée par un harnais interrompu comprise. encodages.json, qui garde les
   vecteurs des messages par construction (plan, D5), n'est pas une trace : il n'est pas lu ici.

Les traces écartées (.jsonl.ecartee) viennent de vraies conversations : contrôlées aussi. Aucun
texte cherché n'est affiché, seulement où et combien. L'identifiant de l'instance se cherche par
scripts/traces.sh : le harnais ne le voit jamais (code-map).

Codes retour : 0 conforme · 1 écart · 2 erreur technique (campagne introuvable, trace illisible).
"""

import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from banc.mesures import CODE, TRACES, Conversation, MesureError, lire
from banc.notation import LECTURE
from banc.traduction import jetons

# Une trace, ou une trace écartée (banc.orchestration).
TRACE = (".jsonl", ".jsonl.ecartee")
# Les clauses d'écriture du Cypher Manual (current, « Clauses » : CREATE, DELETE, DETACH DELETE,
# SET, REMOVE, FOREACH ; MERGE, en lecture et écriture ; INSERT, synonyme GQL de CREATE), et DROP,
# qui retire un index ou une contrainte (lu le 2026-10-18 par context7).
CLAUSES_D_ECRITURE = frozenset(
    {"CREATE", "INSERT", "MERGE", "SET", "DELETE", "REMOVE", "FOREACH", "DROP"}
)
JETON_GOOGLE = b"ya29."
# US4 parle d'un vecteur de « plusieurs centaines de nombres » ; un vecteur de l'index en compte
# 3 072. La plus longue suite des campagnes du jalon 2 (1 784 résultats) en compte 2.
SEUIL_VECTEUR = 100
NOMBRE = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
# Entre deux nombres d'une suite : une virgule, et des blancs, ou leur échappement JSON (un résultat
# indenté de read-cypher, une chaîne dans la ligne de la trace, écrit un nombre par ligne).
BLANCS = r"(?:\s|\\[nrt])*"
SUITE = re.compile(rf"{NOMBRE}(?:{BLANCS},{BLANCS}{NOMBRE})+")


class ControleError(Exception):
    """Contrôle impossible : nom de campagne invalide, campagne sans trace."""


@dataclass(frozen=True)
class Controle:
    """Un contrôle : son libellé, ce qu'il a compté, et ses écarts (vide : conforme)."""

    libelle: str
    obtenu: str
    ecarts: tuple[str, ...] = ()


def commande(campagne: str, *, traces: Path = TRACES, ecrire: Callable[[str], None] = print) -> int:
    """`banc controle-traces` : 0 conforme, 1 écart, 2 erreur technique."""
    try:
        fichiers = fichiers_de(campagne, traces)
        de_traces = [chemin for chemin in fichiers if chemin.name.endswith(TRACE)]
        conversations = [(chemin.name, lire(chemin)) for chemin in de_traces]
        controles = [
            outils(conversations),
            ecritures(conversations),
            jetons_google(fichiers),
            vecteurs(de_traces),
        ]
    except (ControleError, MesureError, OSError, UnicodeDecodeError) as erreur:
        print(f"banc controle-traces : {erreur}", file=sys.stderr)
        return 2
    ecrire(f"campagne {campagne} : {len(de_traces)} traces, {len(fichiers)} fichiers")
    for controle in controles:
        ecrire(f"{'✗' if controle.ecarts else '✓'} {controle.libelle} : {controle.obtenu}")
        for ecart in controle.ecarts:
            ecrire(f"  · {ecart}")
    if ecarts := sum(1 for controle in controles if controle.ecarts):
        ecrire(f"ÉCART : {ecarts} contrôle(s) sur {len(controles)}.")
        return 1
    ecrire(f"CONFORME : {len(controles)} contrôles.")
    return 0


def fichiers_de(campagne: str, traces: Path) -> list[Path]:
    """Les fichiers du dossier d'une campagne, dont au moins une trace. Une autre entrée (un
    dossier) sort de ce qu'une campagne écrit : rien ne la montrerait sûre, erreur."""
    if not CODE.fullmatch(campagne):
        raise ControleError(f"campagne {campagne!r} : un code attendu (minuscules, chiffres, -)")
    dossier = traces / campagne
    entrees = sorted(dossier.iterdir()) if dossier.is_dir() else []
    if autres := [entree.name for entree in entrees if not entree.is_file()]:
        raise ControleError(f"campagne {campagne} : {', '.join(autres)} n'est pas un fichier")
    if not any(entree.name.endswith(TRACE) for entree in entrees):
        raise ControleError(f"campagne {campagne} : aucune trace dans {dossier}")
    return entrees


def outils(conversations: Sequence[tuple[str, Conversation]]) -> Controle:
    """Chaque appel est une lecture read-cypher (US1 : un seul chemin vers la base)."""
    appels = 0
    ecarts = []
    for nom, conversation in conversations:
        for tour in conversation.tours:
            for appel in tour.appels:
                appels += 1
                if appel.outil != LECTURE:
                    ecarts.append(f"{nom}, {tour.question} : {appel.outil}")
    if ecarts:
        return Controle(
            "outils", f"{len(ecarts)} appel(s) hors de {LECTURE} sur {appels}", (*ecarts,)
        )
    return Controle("outils", f"{appels} appels, tous à {LECTURE}")


def ecritures(conversations: Sequence[tuple[str, Conversation]]) -> Controle:
    """Aucune clause d'écriture dans les requêtes, même refusée par le serveur (US1)."""
    requetes = 0
    ecarts = []
    for nom, conversation in conversations:
        for tour in conversation.tours:
            for appel in tour.appels:
                requetes += 1
                if clauses := clauses_d_ecriture(appel.requete):
                    refus = " (refusée par le serveur)" if appel.erreur else ""
                    ecarts.append(f"{nom}, {tour.question} : {', '.join(clauses)}{refus}")
    if ecarts:
        resume = f"{len(ecarts)} requête(s) avec une clause d'écriture sur {requetes}"
        return Controle("écritures", resume, (*ecarts,))
    return Controle("écritures", f"aucune clause d'écriture dans les {requetes} requêtes")


def clauses_d_ecriture(requete: str) -> list[str]:
    """Les clauses d'écriture d'une requête, dans l'ordre, en capitales : un mot de
    CLAUSES_D_ECRITURE, hors chaîne, commentaire et nom entre accents graves, qui n'est ni une
    propriété ni un label (après un point ou deux-points), ni une clé de map (avant deux-points)."""
    utiles = [jeton for jeton in jetons(requete) if jeton.genre not in {"espace", "commentaire"}]
    clauses = []
    for rang, jeton in enumerate(utiles):
        # Seul un nom peut égaler un mot nu : une chaîne, un nom entre accents graves ou un
        # paramètre gardent leurs délimiteurs dans leur texte.
        if jeton.texte.upper() not in CLAUSES_D_ECRITURE:
            continue
        avant = utiles[rang - 1].texte if rang else ""
        apres = utiles[rang + 1].texte if rang + 1 < len(utiles) else ""
        if avant not in {".", ":"} and apres != ":":
            clauses.append(jeton.texte.upper())
    return clauses


def jetons_google(fichiers: Sequence[Path]) -> Controle:
    """Aucun jeton d'accès Google dans les fichiers de la campagne, lus en octets, tels quels."""
    comptes = ((chemin.name, chemin.read_bytes().count(JETON_GOOGLE)) for chemin in fichiers)
    ecarts = [f"{nom} : {nombre} occurrence(s)" for nom, nombre in comptes if nombre]
    motif = f"« {JETON_GOOGLE.decode()} »"
    if ecarts:
        resume = f"{motif} dans {len(ecarts)} fichier(s) sur {len(fichiers)}"
        return Controle("jetons Google", resume, (*ecarts,))
    return Controle("jetons Google", f"aucun {motif} dans les {len(fichiers)} fichiers")


def vecteurs(de_traces: Sequence[Path]) -> Controle:
    """Aucune suite de SEUIL_VECTEUR nombres ou plus dans les traces (US4), ligne par ligne."""
    ecarts = []
    touchees = set()
    for chemin in de_traces:
        lignes = chemin.read_text(encoding="utf-8").splitlines()
        for numero, texte in enumerate(lignes, start=1):
            for taille in suites(texte):
                touchees.add(chemin.name)
                ecarts.append(
                    f"{chemin.name}, ligne {numero} ({_question(texte)}) : {taille} nombres"
                )
    seuil = f"{SEUIL_VECTEUR} nombres ou plus"
    if ecarts:
        resume = (
            f"{len(ecarts)} suite(s) de {seuil} dans {len(touchees)} trace(s) sur {len(de_traces)}"
        )
        return Controle("vecteurs", resume, (*ecarts,))
    return Controle("vecteurs", f"aucune suite de {seuil} dans les {len(de_traces)} traces")


def suites(texte: str) -> list[int]:
    """La taille des suites de SEUIL_VECTEUR nombres ou plus d'un texte, dans l'ordre."""
    tailles = (suite.group().count(",") + 1 for suite in SUITE.finditer(texte))
    return [taille for taille in tailles if taille >= SEUIL_VECTEUR]


def _question(texte: str) -> str:
    """La question d'une ligne de trace, ou « coupée » si elle ne se lit pas (harnais interrompu en
    pleine écriture). Une ligne entière vient d'un tour : banc.mesures.lire l'a déjà relue, et
    l'en-tête ne compte jamais deux nombres de suite."""
    try:
        return str(json.loads(texte)["question"])
    except json.JSONDecodeError:
        return "coupée"
