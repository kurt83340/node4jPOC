# Research — Socle de données

> Brainstorm options pour la feature `001-socle-donnees`.
> Rempli avec méthode par `/conception 001-socle-donnees` (explore → options → décision → revue adverse) — ou à la main en suivant les sections.
> Append des sections datées au fil des pivots/explorations ultérieures.

**Date :** 2026-09-28

## Problème à résoudre

Charger les CSV PokéAPI (textes en français) dans AuraDB Free avec un script réexécutable sans doublons, selon un modèle de graphe documenté, puis établir en Cypher les réponses attendues des questions de référence (10 dans le brief, 30 depuis le 2026-09-29). Deux choix à trancher avant de coder : l'outil ou le langage du chargement, et la variante du modèle (espèces ou formes, descriptions, attaques).

## Contraintes retenues

- **Cadrage** : AuraDB Free, dont la vraie limite reste à noter à la création (au pire 50 000 nœuds et 175 000 relations) ; pause après 72 h sans activité. Identifiants dans `.env`, jamais affichés ni committés. Aucune stack imposée. Objectif d'apprentissage : expliquer chaque choix.
- **ADR-0001** : PokéAPI en français, commit figé, descriptions à dédoublonner, volume d'`APPREND` à surveiller.
- **Code-map** : aucune règle de couplage pour l'instant (projet vierge).
- **Leçons** : aucune (projet vierge).
- **Permissions** : Claude ne peut pas lire `.env` (`settings.json`), donc le script lit lui-même ses identifiants.
- **Jalons suivants** : `neo4j-graphrag` (jalon 3) n'existe qu'en Python (brief), donc le langage du chargement pèse sur la suite.

## Explorations (rapports sourcés)

### Données — PokéAPI (analyse du 2026-09-28)

Commit figé : [`168b1e8`](https://github.com/PokeAPI/pokeapi/tree/168b1e89467054cda2e7df43ccebbb69b459497a/data/v2/csv) (2026-09-26). Tous les chiffres du brief se vérifient sur ce commit.

| Mesure                                                                                          | Valeur                                                                                                                               |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Espèces · noms FR                                                                               | 1 025 · 1 025                                                                                                                        |
| `pokemon.csv` · formes par défaut · formes alternatives                                         | 1 351 · 1 025 · 326 (224 espèces)                                                                                                    |
| Formes alternatives par famille                                                                 | Méga 97 · Gigamax 34 · Alola 20 · Galar 20 · Hisui 16 · Paldea 4 · Totem 11 · autres 124                                             |
| Formes alternatives avec nom FR                                                                 | 326 / 326 (ex. « Deoxys Attaque », « Morphéo Solaire ») ; règle : la `pokemon_form` par défaut, sinon l'unique (8 Koraidon/Miraidon) |
| Types hors des 18 classiques                                                                    | 19 Stellaire · 10001 ??? · 10002 Obscur                                                                                              |
| `type_efficacy` : ×2 · ×0,5 · ×0 · neutre                                                       | 51 · 61 · 8 · 204, soit **120 relations** non neutres                                                                                |
| Descriptions FR · espèces couvertes · textes distincts par espèce                               | 7 116 · 898 · **5 233 (−26 %)** avec `\n` et U+202F remplacés par une espace, puis `trim`                                            |
| `pokemon_moves` : lignes · couples forme–attaque · formes par défaut seules · agrégé par espèce | 638 321 · 99 509 · 79 120 · 80 068                                                                                                   |
| Méthodes d'apprentissage (lignes)                                                               | Capsule 371 571 · Montée de niveau 161 805 · Enseigné 50 075 · Œuf 34 600 · « train » 19 810 · autres < 500                          |
| Attaques · utilisées · avec nom FR                                                              | 937 · 833 · 937                                                                                                                      |
| Talents · utilisés sans nom FR                                                                  | 374 · 3 (`eelevate`, `fire-mane`, `aura-guard`)                                                                                      |
| `EVOLUE_EN` (espèces avec `evolves_from_species_id`) · conditions (`pokemon_evolution`)         | 484 · 676 lignes                                                                                                                     |
| Stats FR (6 par forme, 8 106 lignes)                                                            | PV, Attaque, Défense, Attaque Spéciale, Défense Spéciale, Vitesse                                                                    |
| Habitat renseigné                                                                               | 386 espèces (générations 1 à 3) : grottes, forêts, champs, montagnes, rares, milieux hostiles, mers, urbains, marécages              |

**Contrôles de vraisemblance** : Dracaufeu (espèce 6) est Feu et Vol ; Roche ×4, Eau et Électrik ×2, donc Q1 est confirmée. Le mot « volcan » apparaît dans les descriptions de 16 espèces (Magmar, Magby, Maganon, Camérupt, Heatran, Entei, Sulfura, Tritox…) : piste de réponse de référence pour Q3.

**Pièges relevés** :

- 7 115 descriptions sur 7 116 contiennent des sauts de ligne (boîtes de texte des jeux) : normaliser avant de dédoublonner, sinon doublons ratés et embeddings pollués (jalon 3).
- Méthode « train » (id 12, 19 810 lignes) et 3 talents récents sans nom FR : prévoir un repli sur l'identifiant anglais.
- L'estimation du brief (~10 000 nœuds, ~113 000 relations) correspond à toutes les formes **sans** dédoublonner les descriptions.

**Volume par variante de modèle** (descriptions dédoublonnées) :

| Variante                                                      | Nœuds  | Relations |
| ------------------------------------------------------------- | ------ | --------- |
| Espèces seules (forme par défaut)                             | ~7 360 | ~88 900   |
| Espèces + formes par défaut seulement (schéma à deux niveaux) | ~8 380 | ~89 900   |
| Espèces + toutes les formes                                   | ~8 770 | ~111 800  |

Les trois tiennent dans la limite la plus basse annoncée pour AuraDB Free (50 000 nœuds, 175 000 relations).

### Docs externes

Rapport `explore-docs` du 2026-09-28 (pages officielles consultées ce jour).

**Outils de chargement**

- Pilote Python `neo4j` **6.3.1** (2026-09-15), Python 3.10 à 3.14. Écriture par lots : `driver.execute_query("UNWIND $rows AS r MERGE …", rows=lot, database_="neo4j")`, une transaction gérée et relancée en cas d'erreur passagère. La doc des pilotes ne recommande aucune taille de lot (heuristique d'une doc dépréciée : 1 000 à 20 000 pour des nœuds, 1 000 à 5 000 pour des MERGE de relations). Extension Rust optionnelle `neo4j-rust-ext` (3 à 10 fois plus rapide). Le paquet PyPI `neo4j-driver` est l'ancien nom : ne pas l'installer. [PyPI](https://pypi.org/project/neo4j/) · [performance](https://neo4j.com/docs/python-manual/current/performance/)
- Pilote JavaScript `neo4j-driver` **6.2.0** (2026-06-30), Node LTS (22, 24). Piège : un `number` JS part en décimal, il faut `neo4j.int()` pour les entiers. [npm](https://registry.npmjs.org/neo4j-driver/latest)
- `cypher-shell` **2026.09.0** demande **Java 21** (absent de la machine). Alternative sans Java : `neo4j-cli` v1.14.0, binaire Go de Neo4j Labs, **non supporté officiellement**, qui lit `.env`. [doc](https://neo4j.com/docs/operations-manual/current/cypher-shell/) · [neo4j-cli](https://github.com/neo4j-labs/neo4j-cli)
- `LOAD CSV` sur Aura : http, https et ftp acceptés ; `file:///` et les URI cloud (`gs://`, `s3://`) sont **indisponibles sur Aura**. La lecture depuis raw.githubusercontent.com est autorisée en principe, **à tester**. Tout arrive en chaîne de caractères. Lots : `CALL (row) { … } IN TRANSACTIONS OF n ROWS` (1 000 par défaut, `ON ERROR FAIL`), seulement en transaction implicite (`session.run`, pas `execute_query`). [LOAD CSV](https://neo4j.com/docs/cypher-manual/current/clauses/load-csv/) · [IN TRANSACTIONS](https://neo4j.com/docs/cypher-manual/current/subqueries/subqueries-in-transactions/)
- Import sans code de la console Aura : CSV locaux, modèle dessiné ou chargé en JSON, filtre sur une valeur exacte, **idempotent** (MERGE sur l'ID), une contrainte d'unicité par nœud. Aucune agrégation : `pokemon_moves` serait à pré-agréger. [Import](https://neo4j.com/docs/aura/import/import/)

**Cypher sur Aura**

- Version par défaut : deux pages officielles se contredisent (Cypher 25 par défaut pour les organisations créées depuis 2026.02 selon le manuel, Cypher 5 selon la page Aura). Vérifier avec `SHOW DATABASES YIELD name, defaultLanguage`. Cypher 5 n'évolue plus depuis 2025.06. [manuel](https://neo4j.com/docs/cypher-manual/current/introduction/cypher-aura/) · [Aura](https://neo4j.com/docs/aura/managing-instances/cypher-version/)
- Contraintes : `CREATE CONSTRAINT pokemon_id IF NOT EXISTS FOR (p:Pokemon) REQUIRE p.id IS UNIQUE`. Les contraintes de type (`IS :: INTEGER`) sont marquées « Enterprise Edition » : disponibilité sur Free **à tester**. [doc](https://neo4j.com/docs/cypher-manual/current/schema/constraints/create-constraints/)
- APOC : un sous-ensemble d'APOC Core est préinstallé sur Aura, dont `apoc.meta.schema` (appelé par `get-schema` de `neo4j/mcp` au jalon 2), mais pas `apoc.load.csv`. [doc](https://neo4j.com/docs/aura/apoc/)
- Pièges Cypher 25 : `CALL { WITH line … }` est déprécié (écrire `CALL (line) { … }`) ; `apoc.periodic.iterate` déprécié depuis 2026.04 ; `SET n = r` devient `SET n = properties(r)`.

**AuraDB Free**

- Pause après 72 h sans activité, suppression après 30 jours de pause, **une seule instance Free par compte**. [instance-actions](https://neo4j.com/docs/aura/managing-instances/instance-actions/)
- Limites : les 50 000 nœuds et 175 000 relations de la page produit reprennent l'annonce de lancement de 2021 ; la FAQ (2024) annonce 200 000 et 400 000 ; aucune page de la doc ne donne de chiffre. À relever dans la console à la création.

**Pipeline BigQuery + dbt → Neo4j** (rapport `explore-docs` du 2026-09-28, contexte « entreprise full GCP avec dbt »)

- **Aucun adaptateur dbt pour Neo4j**, ni officiel ni communautaire : dbt s'arrête aux tables BigQuery, le chargement dans Neo4j est une étape à part. [adaptateurs](https://docs.getdbt.com/docs/community-adapters)
- **Tables « en forme de graphe »** : un modèle dbt par label de nœud et par type de relation. Tests `unique` + `not_null` sur chaque clé, `dbt_utils.unique_combination_of_columns` sur les couples d'une relation, `relationships` vers les nœuds (il ignore les NULL, donc `not_null` en plus). Sur BigQuery, les contraintes PK/FK ne sont que déclaratives : les tests restent indispensables. `dbt build` saute ce qui dépend d'un test en échec ; le chargeur Neo4j se déclare en `exposure`. [data tests](https://docs.getdbt.com/reference/resource-properties/data-tests) · [constraints](https://docs.getdbt.com/reference/resource-properties/constraints)
- **Voies BigQuery → Neo4j** :
  - script Python (`google-cloud-bigquery` 3.45.2 + `neo4j` 6.3.1) : le code est à nous, `UNWIND … MERGE` + contraintes, 0 $ ;
  - template Dataflow `Google_Cloud_to_Neo4j` (Preview) : spec JSON v1 (`sources`, `targets`, `actions`), `write_mode: merge` + contrainte indispensables car un lot peut être rejoué jusqu'à 4 fois, colonnes STRUCT/JSON refusées, quelques centimes par import ; [spec](https://neo4j.com/docs/dataflow-bigquery/current/job-specification/)
  - import Aura depuis BigQuery (depuis le 2025-06-09) : clé JSON de compte de service, et une relance n'écrase rien, donc une correction faite dans dbt n'arrive pas dans Neo4j ; [sources](https://neo4j.com/docs/aura/import/data-sources/)
  - connecteur Spark : surdimensionné ici.
- **Aucune voie ne supprime ce qui disparaît de la source** : prévoir une purge.
- **BigQuery** : données brutes chargées par `bq load` (dbt déconseille les seeds pour ça) ; le bac à sable sans carte fait expirer les tables à 60 jours et interdit le DML (pas de modèles `incremental`). [sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox)
- **Orchestration** : à la main pour le POC (`bq load` → `dbt build` → chargeur) ; version entreprise : un Cloud Run job, plus Workflows et Scheduler si besoin, ~0 $.
- **Machine** : `gcloud`, `bq` et Java absents ; Docker présent mais muet (Docker Desktop éteint ?).

**Modélisation** (rapport `explore-docs` du 2026-09-29, avant le gel du modèle) :

- **Nommage** (manuel Cypher, Cypher 25) : labels en PascalCase, relations en SCREAMING_SNAKE_CASE, propriétés en camelCase ; accents permis mais déconseillés ; un identifiant inconnu ne donne qu'un avertissement, donc 0 ligne en silence. [naming](https://neo4j.com/docs/cypher-manual/current/syntax/naming/) · [styleguide](https://neo4j.com/docs/cypher-manual/current/styleguide/)
- **GraphAcademy** : une valeur partagée devient un nœud ; relations spécifiques pour les cas importants, en gardant la générique ; les clés étrangères deviennent des relations, puis disparaissent. Nos degrés sont ordinaires : pas de super-nœud. [modeling fundamentals](https://graphacademy.neo4j.com/courses/modeling-fundamentals)
- **Text-to-Cypher** : Neo4j recommande un schéma enrichi (descriptions, valeurs, exemples), mais `get-schema` de `neo4j/mcp` v1.6.0 ne transmet que labels, propriétés typées et relations. Les identifiants naturels sont corrélés à la justesse (SNAILS, PACMMOD 2025) ; l'effet de la langue du schéma n'a jamais été mesuré avec des LLM récents (Ozsoy et Tai, Neo4j, arXiv 2506.21445). [guide Text2Cypher](https://neo4j.com/blog/genai/text2cypher-guide/)
- **`neo4j-graphrag` 1.21.0** : un index vectoriel sur n'importe quel label suffit ; `Description` reliée au Pokémon convient, sans « lexical graph » ; recherche par la clause `SEARCH` (préfixe `CYPHER 25`).
- **Aura Agent** : agent généré à partir du schéma ; la recherche par similarité accepte `gemini-embedding-001`.
- **`mcp-neo4j-data-modeling`** 0.8.2 (Neo4j Labs) : utile pour dessiner (Mermaid, Arrows) ; sa validation n'est que structurelle.
- → Décisions : [ADR-0005](../../adr/0005-mvp-conventions-nommage-schema.md).

### Conventions du projet (projet vierge)

Rapport `explore-code` du 2026-09-28 (projet vierge : conventions cibles du template).

- **Python** (rules chargées sur `**/*.py`) : ruff (format + check), `mypy --strict`, Python 3.12+, logs structurés et pas de `print` (`.claude/rules/code-style.md`) ; pytest avec 80 % de couverture sur le code métier, `tests/{unit,integration,fixtures}`, intégration sur une vraie base jetable sans simuler la BDD, pas d'appel réseau réel en CI (`.claude/rules/testing.md`). Outillage : `pyproject.toml` + uv ; `uv:*` est pré-autorisé, donc `uv run pytest`, `uv run ruff`, `uv run mypy`.
- **TypeScript** (rules chargées sur ts/js) : mode strict, prettier + eslint ou biome, un seul gestionnaire de paquets, vitest (`.claude/rules/code-style-web.md`, `.claude/rules/testing-web.md`). `npm` est pré-autorisé, `node` et `npx` ne le sont pas.
- **Cypher pur** : aucune rule, aucun outil installé (`cypher-shell` absent), aucune permission. Passer les identifiants de `.env` à l'outil demanderait un script d'appel. Rien pour tester l'idempotence ou les comptes.
- **Transverse** : `.env` est illisible par Claude (`settings.json`), donc le script lit ses identifiants lui-même, et ne doit **jamais** les afficher : tout ce qu'affiche un script lancé par Claude entre dans son contexte. `.env.example` n'a pas encore de bloc Neo4j ; `ACCESS.md` est à créer (premier accès). Aucune règle `.gitignore` pour des CSV locaux, alors que l'ADR-0001 interdit de publier les données.
- **Zone d'ombre** : Docker (repli local, et tests d'intégration « sur vraie base jetable ») n'est pas vérifié sur la machine.

### Mémoire projet

ADR-0001 (jeu de données) et cadrage rédigés le 2026-09-28 ; aucune leçon ni idée (projet vierge).

## Options considérées

> Deux choix indépendants pour le jalon 1. **Julien tranche.**
> Contexte ajouté le 2026-09-28 : l'entreprise de Julien est full GCP avec dbt, et il demande si dbt peut arriver « à la toute fin ».

### Choix 1 — Chaîne de chargement

| Option                                       | Approche                                                                                                                                                                                                                                                                       | Coût                                                                                       | Risques                                                                                                                                                       | Réversibilité                                               | Conforme couplage/ADR ? |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------- |
| **A — Pipeline d'entreprise dès maintenant** | CSV → BigQuery (`bq load`) → dbt (filtre FR, normalisation, agrégation ; une table par nœud et par relation, testées) → chargeur Python (BigQuery → `UNWIND … MERGE`)                                                                                                          | 0 $, mais compte de facturation GCP, `gcloud` et dbt à installer : la plus longue à monter | beaucoup de pièces avant le premier nœud chargé ; dbt v2 très récent                                                                                          | bonne                                                       | ✅ ADR-0001             |
| **B — Python en deux étages, dbt à la fin**  | Étage 1 : transformations Python → tables « en forme de graphe » (une par nœud et par relation, au schéma des futurs modèles dbt). Étage 2 : chargeur Python (`UNWIND … MERGE`). Au jalon final, dbt + BigQuery remplacent l'étage 1 et le chargeur change seulement de source | 0 $, aucun compte GCP pour démarrer                                                        | transformations écrites deux fois (Python, puis SQL) ; le jalon dbt peut glisser                                                                              | très bonne : le contrat des tables rend dbt interchangeable | ✅ ADR-0001             |
| **C — Cypher pur**                           | `LOAD CSV` depuis les URL GitHub du commit figé ; fichiers `.cypher` exécutés par `cypher-shell` (Java 21) ou `neo4j-cli` (Labs)                                                                                                                                               | 0 $                                                                                        | agrégation de 638 000 lignes dans la mémoire d'Aura Free ; Java à installer ou outil non supporté ; non transposable (`LOAD CSV` ne lit pas `gs://` sur Aura) | moyenne                                                     | ✅ ADR-0001             |
| ~~TypeScript~~                               | Écartée : l'écosystème du POC (neo4j-graphrag, ADK, dbt, BigQuery) est en Python                                                                                                                                                                                               | —                                                                                          | —                                                                                                                                                             | —                                                           | —                       |

### Choix 2 — Modèle du graphe

| Option                              | Approche                                                                                          | Volume                           | Pour                                                                                                                                             | Contre                                                                                                   |
| ----------------------------------- | ------------------------------------------------------------------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| **M1 — Espèces seules**             | `Pokemon` = espèce, avec les données de sa forme par défaut                                       | ~7 360 nœuds · ~88 900 relations | le plus simple ; un nom = un nœud                                                                                                                | perd Méga, Gigamax et formes régionales (326 formes) ; les ajouter plus tard change le sens de `Pokemon` |
| **M2 — Espèce + toutes les formes** | `Espece` (nom, descriptions, évolutions) ← `FORME_DE` — `Forme` (types, stats, talents, attaques) | ~8 770 · ~111 800                | fidèle à PokéAPI ; vraie leçon de modélisation (identité et variantes, comme produit et références en entreprise) ; les 326 formes ont un nom FR | requêtes à deux niveaux, plus exigeantes pour le text-to-Cypher                                          |
| **M3 — Espèce + formes par défaut** | schéma de M2, avec les 1 025 formes par défaut seulement                                          | ~8 380 · ~89 900                 | schéma prêt pour les formes                                                                                                                      | la complexité de M2 sans son bénéfice ; charger les formes ensuite ne coûterait qu'une relance           |

**Commun à toutes les variantes** (se tranche dans le plan) : descriptions dédoublonnées (5 233 textes normalisés) ; `APPREND` agrégé par couple, avec méthodes et niveau en propriétés ; efficacités entre types en trois relations nommées (brief) ; stats en propriétés ; Cypher 25 fixé explicitement.

### Recommandation

- **Chargement : B.** Julien (2026-09-28) : dbt fait partie de l'équation de l'entreprise, pas du POC. Aucune technique du banc d'essai n'en dépend : elles interrogent toutes Neo4j. B garde le POC compatible sans rien coûter : l'étage de transformation produit les mêmes tables que produiraient des modèles dbt, donc l'entreprise pourra brancher dbt à la place de l'étage 1, et les transformations Python lui serviront de spécification. A contredit « dbt hors POC » ; C apprend le Cypher de chargement, mais n'est pas transposable.
- **Modèle : M2.** Fidèle à la source, sans risque de volume pour Aura Free, et un text-to-Cypher plus exigeant rend le banc d'essai plus instructif.

## Décision

Décidé par Julien le 2026-09-28 :

- **Chargement : C, Cypher pur**, contre la recommandation B. L'objectif n°1 est d'apprendre Neo4j, et la transposabilité du script ne compte plus puisque dbt sort du POC ([ADR-0002](../../adr/0002-cadrage-environnement-cible-google-cloud.md)). Pourquoi pas B : moins de Cypher pratiqué ; pas A : contredit « dbt hors POC ». → [ADR-0003](../../adr/0003-mvp-chargement-cypher-pur.md)
- **Modèle : M2, espèce + toutes les formes.** Pourquoi pas M1 : perd les 326 formes ; pas M3 : la complexité de M2 sans son bénéfice. → [ADR-0004](../../adr/0004-mvp-modele-espece-formes.md)
- Décisions locales (sources, clés, agrégation, descriptions, Cypher 25, mode d'exécution) : § Décisions du [plan](plan.md).

## Revue adverse

Revue du 2026-09-28 par l'agent `reviewer` (contexte frais, mesures sur les CSV du commit figé et doc Neo4j à jour). Toutes les corrections sont intégrées au [plan](plan.md) et aux [tâches](tasks.md).

- 🔴 **Normalisation des descriptions** : remplacer seulement `\n` donne 5 240 textes, pas 5 233 ; il faut aussi remplacer l'espace fine insécable U+202F (310 occurrences). → règle écrite dans le plan (D4).
- 🟠 **Go/no-go trop faible** : il ne testait ni les champs multilignes, ni les gros fichiers, ni la fin de ligne Windows de `pokemon_abilities.csv`. → go/no-go étendu (T2.2).
- 🟠 **Cypher 25** : préfixer chaque requête laisserait les agents des jalons suivants en Cypher 5. → langue par défaut de la base (D7).
- 🟠 **Installation** : `cypher-shell` n'est pas dans les dépôts apt configurés. → `.deb` officiel installé par `apt` (D9).
- 🟠 **Noms des formes** : jointure `pokemon_forms` / `pokemon_form_names` absente et piégée (Koraidon/Miraidon). → règle « par défaut, sinon l'unique » et contrôle des doublons (D6).
- 🟠 **Questions avant les propriétés** : la matrice question → propriétés et le modèle documenté passent avant la vérification (D10, T1.2).
- 🟠 **Critères de fin trop faibles** : codes retour 0 / 1 / 2, comptes par motif, empreintes pour l'idempotence (D8).
- 🟠 **Durées** : un appel Bash est coupé à 10 min. → chargements en arrière-plan, idempotence dans sa propre phase.
- 🟠 **Réponses rejouables** : ordre total, listes triées, Q2 vérifiée par une requête, Q3 en deux ensembles (D11).
- 🟠 **Purge** : `MERGE` n'efface rien. → `charger.sh --purge`.
- 🟠 **Limite de l'instance** : critères de la spec sans tâche. → notée en T2.1, comparée par `verifier.sh`.
- 🟢 Sécurité : ne lire que 4 variables de `.env`, protéger le fichier `Neo4j-*.txt`. Niveau d'`APPREND` : minimum tous jeux confondus, à ne pas utiliser comme vérité. `EVOLUE_EN` en deux passes. 313 talents utilisés. Repli par URL signée plutôt que bucket public.
- ✅ Jugé solide : tous les comptes (18 · 120 · 1 025 · 484 · 1 351 · 919 · 99 509 · 2 116 · 2 943 · 5 233 avec la bonne règle), Q1, contraintes composites hors Enterprise, `IN TRANSACTIONS` via `cypher-shell -f`, LOAD CSV https sur Aura, idempotence de l'agrégation d'`APPREND`.

## Liens externes

- [PokéAPI — CSV au commit figé](https://github.com/PokeAPI/pokeapi/tree/168b1e89467054cda2e7df43ccebbb69b459497a/data/v2/csv)
- [ADR-0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md)
