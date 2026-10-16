"""Index vectoriel et encodage des descriptions (spec 003, T4.1 ; plan D2 et D3), sur leur texte,
sans base ni dépense : rien ne touche Aura ni Vertex avant la phase 6.

cypher/00-contraintes.cypher porte l'index descriptions_texte (3 072 dimensions, cosine, sans
quantification), que banc anglais traduit tel quel, au nom près. cypher/07-embeddings.cypher prend
les descriptions sans vecteur par lots de 100, un lot par transaction et sans CONCURRENT, les encode
par ai.text.embedBatch (gemini-embedding-001, RETRIEVAL_DOCUMENT en snake_case, europe-west1), le
jeton et le projet en paramètres, rattache chaque vecteur par l'index rendu, rend le nombre encodé
et attend l'index. Le code se lit sans ses commentaires, chaque suite d'espaces réduite à une
espace : un commentaire ne fait ni passer ni échouer un contrôle.
"""

import re
from pathlib import Path

from banc import correspondance
from banc.traduction import jetons

RACINE = Path(__file__).resolve().parents[2]
CONTRAINTES = RACINE / "cypher" / "00-contraintes.cypher"
CONTRAINTES_EN = RACINE / "cypher" / "anglais" / "contraintes.cypher"
ENCODAGE = RACINE / "cypher" / "07-embeddings.cypher"
INDEX = re.compile(
    r"CREATE VECTOR INDEX (?P<nom>\w+) IF NOT EXISTS FOR \((?P<variable>\w+):(?P<label>\w+)\) "
    r"ON (?P=variable)\.(?P<cle>\w+) OPTIONS \{indexConfig: \{(?P<reglages>[^{}]*)\}\};"
)
APPEL = re.compile(
    r"CALL ai\.text\.embedBatch\(\[(?P<variable>\w+) IN (?P<lot>\w+) \| (?P=variable)\.texte\], "
    r"(?P<fournisseur>'\w+'), \{(?P<configuration>.*)\}\) YIELD index, vector "
)
LOTS = re.compile(
    r"UNWIND range\(0, (?P<total>\w+) - 1, (?P<taille>\d+)\) AS (?P<debut>\w+) "
    r"CALL \((?P<liste>\w+), (?P=debut)\) \{ WITH (?P=liste)\[(?P=debut) \.\. (?P=debut) \+ "
    r"(?P<tranche>\d+)\] AS (?P<lot>\w+) "
)
# Une clé de map et sa valeur : littéral, paramètre, nombre, ou map sans map dedans.
CLE = re.compile(r"`?(?P<cle>[\w.]+)`?: (?P<valeur>'[^']*'|\$\w+|\d+|\{[^{}]*\})")


def code(chemin: Path) -> str:
    """Le texte Cypher sans ses commentaires, chaque suite d'espaces réduite à une espace."""
    texte = "".join(j.texte for j in jetons(chemin.read_text()) if j.genre != "commentaire")
    return " ".join(texte.split())


def carte(texte: str) -> dict[str, str]:
    """Les clés d'une map et leurs valeurs, sans ses accolades."""
    return {m["cle"]: m["valeur"] for m in CLE.finditer(texte)}


def index_vectoriel(chemin: Path) -> re.Match[str]:
    [trouve] = INDEX.finditer(code(chemin))
    return trouve


def appel() -> re.Match[str]:
    trouve = APPEL.search(code(ENCODAGE))
    assert trouve is not None, "appel à ai.text.embedBatch introuvable"
    return trouve


def configuration() -> dict[str, str]:
    return carte(appel()["configuration"])


def options_vertex() -> dict[str, str]:
    return carte(configuration()["vendorOptions"][1:-1])


# --- L'index (00-contraintes.cypher, D2) --------------------------------------------------------


def test_index_des_descriptions() -> None:
    index = index_vectoriel(CONTRAINTES)
    assert (index["nom"], index["label"], index["cle"]) == (
        "descriptions_texte",
        "Description",
        "embedding",
    )


def test_reglages_de_l_index() -> None:
    # 3 072 dimensions, le défaut du modèle, celui qu'Aura Agent servira (jalon 4) ; cosine ; sans
    # quantification : le défaut binary rogne le rappel, et 5 233 vecteurs ne pèsent que 64 Mo.
    assert carte(index_vectoriel(CONTRAINTES)["reglages"]) == {
        "vector.dimensions": "3072",
        "vector.similarity_function": "'cosine'",
        "vector.quantization.type": "'none'",
    }


def test_index_anglais_au_nom_pres() -> None:
    # banc anglais traduit 00-contraintes.cypher : seul le nom de l'index change, d'après
    # correspondance.toml.
    francais, anglais = index_vectoriel(CONTRAINTES), index_vectoriel(CONTRAINTES_EN)
    nom = correspondance.charger().nom("index", francais["nom"], "en")
    assert (nom, anglais["nom"]) == ("descriptions_text", "descriptions_text")
    assert anglais.groupdict() | {"nom": None} == francais.groupdict() | {"nom": None}


# --- L'encodage (07-embeddings.cypher, D3) ------------------------------------------------------


def test_descriptions_sans_vecteur_seulement() -> None:
    # Une relance n'encode que ce qui manque, sans repayer.
    debut = "MATCH (d:Description) WHERE d.embedding IS NULL WITH collect(d) AS descriptions, "
    assert code(ENCODAGE).startswith(debut + "count(*) AS total UNWIND ")


def test_lots_de_100() -> None:
    # 100 textes font environ 3 300 jetons, loin des 250 textes et 20 000 jetons d'une requête.
    lots = LOTS.search(code(ENCODAGE))
    assert lots is not None, "lots introuvables"
    assert (lots["total"], lots["liste"], lots["lot"]) == ("total", "descriptions", appel()["lot"])
    assert lots["taille"] == lots["tranche"] == "100"


def test_un_lot_par_transaction_sans_concurrence() -> None:
    # Un lot à la fois : des appels en parallèle s'exposeraient aux 429 de Vertex.
    texte = code(ENCODAGE)
    assert texte.count("} IN TRANSACTIONS OF 1 ROW ") == 1
    assert "CONCURRENT" not in texte.upper()


def test_fournisseur_vertex() -> None:
    # Le nom que la doc du plugin donne au fournisseur (« Version 25 (Current) », lue le
    # 2026-10-16).
    assert appel()["fournisseur"] == "'vertexai'"


def test_modele_et_region() -> None:
    # Le modèle des questions (banc.encodage, D5) ; europe-west1, la région de l'instance : eu
    # renvoie 404 pour ce modèle (test du 2026-10-12).
    reglages = configuration()
    assert (reglages["model"], reglages["region"]) == ("'gemini-embedding-001'", "'europe-west1'")


def test_aucune_autre_cle_de_configuration() -> None:
    # Ni apiKey, sans échéance, ni maxBatchSize : les lots de 100 bornent déjà chaque requête.
    assert set(configuration()) == {"model", "project", "region", "token", "vendorOptions"}


def test_task_type_en_snake_case() -> None:
    # Le seul que le plugin transmet : taskType serait ignoré sans erreur, et les vecteurs pris en
    # RETRIEVAL_QUERY, le défaut de Vertex (test payant du 2026-10-12).
    assert options_vertex() == {
        "task_type": "'RETRIEVAL_DOCUMENT'",
        "outputDimensionality": "3072",
    }


def test_dimension_de_l_index() -> None:
    dimensions = carte(index_vectoriel(CONTRAINTES)["reglages"])["vector.dimensions"]
    assert options_vertex()["outputDimensionality"] == dimensions


def test_jeton_en_parametre() -> None:
    # Le jeton d'aura-genai arrive par une ligne :param sur stdin (ADR-0019), jamais écrit dans le
    # fichier.
    assert configuration()["token"] == "$jeton"
    assert ":param" not in code(ENCODAGE)
    assert "ya29." not in ENCODAGE.read_text()


def test_projet_en_parametre() -> None:
    # Rien en dur dans cypher/ (code-map) : charger.sh passe le projet du compte emprunté
    # (commun.sh).
    assert configuration()["project"] == "$projet"
    assert "jleroy" not in ENCODAGE.read_text()


def test_parametres_du_fichier() -> None:
    # Ce que charger.sh devra passer à 07 (T5.1), ni plus ni moins.
    assert set(re.findall(r"\$\w+", code(ENCODAGE))) == {"$jeton", "$projet"}


def test_vecteur_rattache_par_son_index() -> None:
    # Jamais par le texte : celui des six Ultra-Chimères est en double.
    texte, lot = code(ENCODAGE), appel()["lot"]
    assert f" YIELD index, vector WITH {lot}[index] AS d, vector SET d.embedding = vector " in texte
    assert re.findall(r"\w+\.texte\b", texte) == [f"{appel()['variable']}.texte"]
    assert "texte:" not in texte


def test_nombre_encode_rendu() -> None:
    # Par lot, puis en tout : 0 si rien ne manque ; --idempotence l'exigera au second chargement
    # (T5.1).
    fin = "RETURN count(*) AS encodees } IN TRANSACTIONS OF 1 ROW RETURN sum(encodees) AS encodees;"
    assert code(ENCODAGE).count(fin) == 1


def test_attente_de_l_index() -> None:
    # 10 minutes, le seuil du circuit breaker du plan, sur l'index de 00-contraintes.cypher.
    nom = index_vectoriel(CONTRAINTES)["nom"]
    assert code(ENCODAGE).endswith(f"; CALL db.awaitIndex('{nom}', 600);")
