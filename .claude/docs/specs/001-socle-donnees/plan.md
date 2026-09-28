# Plan — Socle de données

> COMMENT on implémente la feature `001-socle-donnees`.

**Date :** 2026-09-28 (revue adverse intégrée le même jour : [research § Revue adverse](research.md))
**Décisions de Julien :** chargement en Cypher pur ([ADR-0003](../../adr/0003-mvp-chargement-cypher-pur.md)), modèle espèce + formes ([ADR-0004](../../adr/0004-mvp-modele-espece-formes.md)).

## Approche technique

Des fichiers `.cypher`, un par groupe de données, lisent les CSV PokéAPI du commit figé `168b1e8` depuis GitHub (`LOAD CSV WITH HEADERS FROM $base + '/pokemon.csv'`). L'URL de base est un paramètre (`cypher-shell -P`), ce qui permet de changer de source sans toucher aux fichiers. Chaque écriture est un `MERGE` sur une clé couverte par une contrainte d'unicité : relancer un fichier ne crée aucun doublon. Les gros fichiers passent par `CALL (row) { … } IN TRANSACTIONS OF n ROWS`, qui découpe le travail en lots pour ménager la mémoire d'Aura Free. La base est réglée une fois pour toutes en Cypher 25 (langue par défaut). `scripts/charger.sh` exécute les fichiers dans l'ordre avec `cypher-shell`, en arrière-plan avec un journal horodaté par fichier, et transmet les identifiants sans jamais les afficher. La vérification s'écrit **avant** le chargement : `scripts/verifier.sh` compare la base aux comptes et empreintes attendus ; il signale un écart sur une base vide, puis passe au vert étape par étape.

## Architecture

```
GitHub : CSV PokéAPI au commit 168b1e8  (URL de base = paramètre $base)
        │  https — LOAD CSV, exécuté côté serveur Aura
        ▼
scripts/charger.sh ──► cypher-shell ──► AuraDB Free (Cypher 25 par défaut)
  --ping · --go-no-go · --purge          exécute cypher/00 → 06 dans l'ordre,
  (4 variables lues dans .env)           en arrière-plan, journal par fichier
scripts/verifier.sh ──► cypher/90-verification.cypher
  codes retour : 0 = conforme · 1 = écart · 2 = erreur technique
scripts/questions.sh ──► questions/qNN.cypher ──► questions/attendu/qNN.txt
```

Modèle (notation Cypher ; propriétés figées après la matrice questions → propriétés, T1.2) :

```
(:Espece)-[:EVOLUE_EN {declencheur, niveau_min, …}]->(:Espece)
(:Espece)-[:A_POUR_DESCRIPTION]->(:Description {texte, jeux})
(:Forme {par_defaut, pv, attaque, defense, …})-[:FORME_DE]->(:Espece)
(:Forme)-[:A_LE_TYPE {slot}]->(:Type)
(:Forme)-[:A_LE_TALENT {cache}]->(:Talent)
(:Forme)-[:APPREND {methodes, niveau}]->(:Attaque {puissance, categorie, …})
(:Attaque)-[:A_LE_TYPE]->(:Type)
(:Type)-[:SUPER_EFFICACE_CONTRE | PEU_EFFICACE_CONTRE | SANS_EFFET_CONTRE]->(:Type)
```

## Modules / fichiers impactés

| Fichier                                                                    | Action  | Notes                                                                                                                         |
| -------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `cypher/00-contraintes.cypher`                                             | nouveau | une contrainte d'unicité par label, composite (espèce, texte) pour `Description`                                              |
| `cypher/01-types.cypher`                                                   | nouveau | 18 types, 120 efficacités                                                                                                     |
| `cypher/02-especes.cypher`                                                 | nouveau | 1 025 espèces, noms et catégories FR ; `EVOLUE_EN` (484) en seconde passe                                                     |
| `cypher/03-formes.cypher`                                                  | nouveau | 1 351 formes, `FORME_DE`, stats, `A_LE_TYPE` ; noms via `pokemon_forms` + `pokemon_form_names`                                |
| `cypher/04-talents.cypher`                                                 | nouveau | 313 talents utilisés, `A_LE_TALENT`                                                                                           |
| `cypher/05-attaques.cypher`                                                | nouveau | 919 attaques (sans les 18 attaques Obscur, jamais apprises), leur type ; `APPREND` agrégé : 638 321 lignes → 99 509 relations |
| `cypher/06-descriptions.cypher`                                            | nouveau | 5 233 descriptions normalisées et dédoublonnées, liste des jeux                                                               |
| `cypher/90-verification.cypher`                                            | nouveau | comptes par motif `(label)-[type]->(label)`, empreintes, doublons de noms                                                     |
| `scripts/charger.sh`                                                       | nouveau | options `--ping`, `--go-no-go`, `--purge` ; chargement en arrière-plan journalisé                                             |
| `scripts/verifier.sh`                                                      | nouveau | comptes, empreintes, limite de l'instance ; codes retour 0 / 1 / 2 ; option `--idempotence`                                   |
| `scripts/questions.sh`                                                     | nouveau | rejoue les 10 requêtes et compare aux réponses enregistrées                                                                   |
| `questions/README.md`, `questions/qNN.cypher`, `questions/attendu/qNN.txt` | nouveau | le banc d'essai : question, technique visée, requête, réponse attendue                                                        |
| `.env.example`, `.gitignore`                                               | modif   | 4 variables `NEO4J_*` sans valeur ; `Neo4j-*.txt` ignoré                                                                      |
| `.claude/settings.json`                                                    | modif   | lecture de `Neo4j-*.txt` interdite (via `/update-config`)                                                                     |
| `.claude/docs/ACCESS.md`                                                   | nouveau | où récupérer les identifiants Aura (jamais leur valeur)                                                                       |
| `.claude/docs/conception/ARCHITECTURE.md`                                  | modif   | § 1 schéma du modèle, § 5 correspondance CSV → graphe (dès T1.2)                                                              |
| `.claude/docs/code-map.md`, `.claude/docs/stack.md`                        | modif   | vue macro et règles de couplage ; Neo4j, Cypher 25, cypher-shell, commit PokéAPI                                              |

CSV lus (commit figé) : `languages`, `types`, `type_names`, `type_efficacy`, `pokemon_species`, `pokemon_species_names`, `pokemon_evolution` (+ tables de déclencheurs et d'objets si la matrice les demande), `pokemon`, `pokemon_forms`, `pokemon_form_names`, `pokemon_stats`, `pokemon_types`, `abilities`, `ability_names`, `pokemon_abilities`, `moves`, `move_names`, `move_damage_class_prose`, `pokemon_moves`, `pokemon_move_method_prose`, `pokemon_species_flavor_text`, `versions` et `version_names` (jeux des descriptions), `pokemon_habitat_names` si la matrice le demande.

## Flux de données

0. **Purge** (optionnelle, `--purge`) : `DETACH DELETE` par lots puis suppression des contraintes, pour repartir d'une base vide.
1. **Contraintes** (00), avant tout `MERGE` : elles créent l'index qui rend `MERGE` rapide et interdisent les doublons.
2. **Nœuds de référence** (01 → 04) : types, espèces, formes, talents. Les relations entre nœuds d'un même fichier se font en seconde passe (17 évolutions ont leur espèce source après leur cible dans le CSV).
3. **Gros volumes** (05 → 06) : attaques et `APPREND`, puis descriptions, en lots.
4. **Vérification** (90) : comptes, empreintes, doublons de noms, limite de l'instance.
5. **Questions** (qNN) : réponses de référence enregistrées, rejouables.

## Erreurs / cas limites

| Cas                                                                                                          | Comportement attendu                                                                                                                                                                                                              |
| ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Aura refuse la lecture depuis GitHub                                                                         | le go/no-go échoue : repli sur une URL signée Cloud Storage, passée en paramètre `$base` (pas de bucket public : l'ADR-0001 interdit de republier les données) ; sinon retour en conception                                       |
| Champs multilignes entre guillemets (7 115 descriptions) ; fin de ligne Windows dans `pokemon_abilities.csv` | testés au go/no-go ; `trim` avant toute conversion (`toInteger(trim(row.slot))`)                                                                                                                                                  |
| Coupure au milieu d'un lot (`IN TRANSACTIONS`)                                                               | les lots validés restent : relancer le fichier, `MERGE` ne crée aucun doublon                                                                                                                                                     |
| Version corrigée d'un fichier (propriété renommée, règle changée)                                            | `MERGE` n'efface rien : `--purge`, puis rechargement complet                                                                                                                                                                      |
| Nom FR manquant (méthode « train », 3 talents récents)                                                       | repli sur l'identifiant anglais (`coalesce`)                                                                                                                                                                                      |
| Nom d'une forme                                                                                              | la `pokemon_form` par défaut, sinon l'unique (8 formes Koraidon/Miraidon n'ont qu'une `pokemon_form`, marquée non par défaut) ; forme par défaut sans nom de forme : nom de l'espèce ; contrôle des noms en double                |
| Types hors des 18 classiques (Stellaire, ???, Obscur)                                                        | ignorés, ainsi que les 18 attaques Obscur (aucun Pokémon ne les apprend)                                                                                                                                                          |
| Descriptions : sauts de ligne (7 115) et espaces fines insécables U+202F (310)                               | `trim(replace(replace(t, '\n', ' '), ' ', ' '))`, puis dédoublonnage par `MERGE` sur (espèce, texte) : 5 233 textes                                                                                                               |
| Niveau d'`APPREND`                                                                                           | niveau minimal tous jeux confondus : 420 couples à 0 (appris à l'évolution), et 10 578 des 22 573 couples appris par montée de niveau changent de niveau selon le jeu. Documenté ; aucune réponse de référence ne s'appuie dessus |
| Instance Free en pause (72 h) ou supprimée (30 jours de pause)                                               | la relancer depuis la console, ou la recréer puis tout recharger                                                                                                                                                                  |
| Appel Bash coupé à 10 min                                                                                    | chargements lancés en arrière-plan, journal horodaté par fichier                                                                                                                                                                  |

## Décisions (locales à cette feature)

> Décisions tech **locales** à cette spec uniquement. Si cross-feature → promouvoir en ADR via `/adr`.

### D1 — Source des CSV : GitHub au commit figé, URL de base en paramètre

**Choix :** `$base` = `https://raw.githubusercontent.com/PokeAPI/pokeapi/168b1e8…/data/v2/csv`, passé par `cypher-shell -P`.
**Pourquoi :** reproductible (ADR-0001), aucun hébergement à gérer, les données ne sont pas copiées dans le dépôt, et changer de source ne touche aucun fichier `.cypher`.
**Alternatives écartées :** fichiers locaux (`file:///` indisponible sur Aura) ; bucket Cloud Storage public (republie les données) ; une URL signée reste le repli.

### D2 — Clés : identifiants PokéAPI

**Choix :** l'`id` entier de PokéAPI pour `Espece`, `Forme`, `Type`, `Attaque`, `Talent` ; le couple (espèce, texte) pour `Description`.
**Pourquoi :** stables et déjà uniques, ils permettent un `MERGE` idempotent.
**Alternatives écartées :** les noms FR (non uniques entre formes).

### D3 — `APPREND` agrégé en Cypher, par lots

**Choix :** `MERGE` de la relation, ajout de la méthode seulement si elle manque, niveau minimal de montée de niveau ; lots de 5 000 lignes.
**Pourquoi :** 638 321 lignes deviennent 99 509 relations sans outil externe ; l'union et le minimum sont idempotents et indépendants de l'ordre des lots (vérifié en revue).
**Alternatives écartées :** pré-agrégation hors Neo4j (contraire à l'ADR-0003 ; repli seulement si le coupe-circuit se déclenche).

### D4 — Descriptions : une par texte distinct et par espèce

**Choix :** normalisation `trim(replace(replace(t, '\n', ' '), ' ', ' '))`, `MERGE` sur (espèce, texte), liste des jeux en propriété.
**Pourquoi :** 26 % de nœuds en moins et pas de doublons dans la future recherche vectorielle (jalon 3). Sans la seconde substitution, on obtient 5 240 textes au lieu de 5 233.

### D5 — Attaques : type, puissance, catégorie

**Choix :** `(:Attaque)-[:A_LE_TYPE]->(:Type)`, plus la puissance et la catégorie (physique, spéciale, statut).
**Pourquoi :** Q1 (« quelles attaques font le plus mal ») en a besoin ; le modèle du brief ne les avait pas.

### D6 — Noms en français, identifiants anglais en repli

**Choix :** propriété `nom` en français, `identifiant` anglais de PokéAPI à côté ; règle des noms de formes ci-dessus.
**Pourquoi :** les questions sont en français, et le text-to-Cypher lira les noms.

### D7 — Cypher 25 comme langue par défaut de la base

**Choix :** `ALTER DATABASE <base> SET DEFAULT LANGUAGE CYPHER 25` au go/no-go, contrôlé par `SHOW DATABASES` ; nom de la base lu dans le fichier d'identifiants.
**Pourquoi :** les agents des jalons suivants (MCP, Aura Agent, graphrag) ne préfixent pas leurs requêtes : ils doivent tourner dans le même Cypher que la vérité de référence. Un préfixe oublié ne donnerait aucune erreur.
**Alternatives écartées :** préfixer chaque requête par `CYPHER 25`.

### D8 — Mode d'exécution : vérification d'abord

**Choix :** écrire `verifier.sh` avant de charger. Codes retour : 0 conforme, 1 écart, 2 erreur technique ; comptes par motif `(label)-[type]->(label)` ; empreintes (`sum(size(r.methodes))`, `sum(r.niveau)`, `sum(size(d.jeux))`) ; noms en double ; volume comparé à la vraie limite de l'instance. Les réponses des 10 questions se vérifient après coup.
**Pourquoi :** les comptes sont connus à l'avance (analyse du commit figé) ; le test rouge devient le point de vérification de chaque étape, et les empreintes détectent une relance qui ferait grossir les listes sans changer les comptes.

### D9 — Outillage : `cypher-shell` officiel

**Choix :** Java 21 par `apt` ; `cypher-shell` 2026.09.0 depuis `https://dist.neo4j.org/cypher-shell/cypher-shell_2026.09.0_all.deb`, installé par `sudo apt install ./…deb` en arrière-plan.
**Alternatives écartées :** le dépôt apt de Neo4j (l'ajouter demande un sudo hors apt, donc le mot de passe de Julien) ; `neo4j-cli` (Neo4j Labs, non supporté) et l'archive `.zip` sans sudo restent en repli.

### D10 — Les questions avant les propriétés

**Choix :** les 10 questions (T1.1), puis une matrice question → labels et propriétés, et le modèle documenté dans `ARCHITECTURE.md` (T1.2), figé avant d'écrire la vérification.
**Pourquoi :** des données probablement utiles ne sont pas encore au modèle (conditions d'évolution, habitat, génération, légendaire) : on ne charge que ce qu'une question demande.

### D11 — Réponses de référence rejouables

**Choix :** `ORDER BY` total, listes triées (`COLLECT { … ORDER BY … }`), `--format plain`, SHA du commit PokéAPI en en-tête. Q2 (« équipe de 6 ») : une requête qui vérifie une équipe proposée, pas une réponse figée. Q3 (« volcans ») : un ensemble obligatoire (16 espèces citant « volcan ») et un ensemble acceptable (magma, cratère, lave…).
**Pourquoi :** un diff texte n'est stable après rechargement qu'avec un ordre total ; certaines questions ont plusieurs bonnes réponses.

## Sécurité

- `charger.sh` n'exécute pas `.env` : il en extrait seulement `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` et `NEO4J_DATABASE`, que `cypher-shell` lit tout seul dans l'environnement. Jamais en argument de commande, `set +x`, jamais `--debug`, et le script vérifie que le mot de passe n'apparaît pas dans sa propre sortie.
- Le fichier d'identifiants téléchargé depuis Aura (`Neo4j-*.txt`) est ignoré par git et sa lecture est interdite à Claude.
- `.env.example` ne contient que les noms des variables ; `ACCESS.md` dit où récupérer le fichier d'identifiants.
- Les CSV ne sont pas copiés dans le dépôt, ni republiés (univers Pokémon © Nintendo, ADR-0001).
- gitleaks en pre-commit.

## Performance

- Cible : chargement complet en moins de 15 min sur Aura Free ; `APPREND` domine.
- Chargements en arrière-plan, journal horodaté par fichier (un appel Bash au premier plan est coupé à 10 min).
- Lots de 5 000 lignes pour `APPREND` (heuristique Neo4j : 1 000 à 5 000 pour des `MERGE` de relations), 1 000 par défaut ailleurs.
- Contraintes créées avant tout `MERGE`.

## Tests

- **Comptes et empreintes** : `scripts/verifier.sh` (voir D8). Attendus : 8 859 nœuds et 112 675 relations au total, sous la vraie limite de l'instance.
- **Idempotence** : purge, chargement, empreinte, second chargement, même empreinte (`verifier.sh --idempotence`).
- **Vraisemblance** : Q1 (Roche ×4 contre Dracaufeu), 16 espèces dont la description cite « volcan », aucun nom de forme en double.
- **Questions** : `scripts/questions.sh` rejoue les 10 requêtes ; les sorties doivent être identiques aux réponses enregistrées.

## Circuit breakers (conditions d'arrêt — à définir AVANT de coder)

> Si une condition se déclenche : STOP — on ne s'acharne pas. Retour `/conception 001-socle-donnees`
> (replanifier) ou parking documenté (ROADMAP + HANDOFF § Blocked on).

- Go/no-go en échec (Aura ne lit pas GitHub, ou mal les champs multilignes) → repli sur une URL signée ; s'il échoue aussi → retour en conception (le Cypher pur perd son intérêt).
- `APPREND` : plus de 15 min ou erreur mémoire sur Aura Free, deux fois de suite → STOP, proposer à Julien une pré-agrégation hors Neo4j (écart à l'ADR-0003, à valider).
- 3 échecs consécutifs sur la même tâche → l'approche est mauvaise, replanifier.
- Instance ou identifiants absents → parking : action de Julien (ROADMAP, HANDOFF « Blocked on »).

## Liens

- Spec : [spec.md](spec.md)
- Research : [research.md](research.md)
- Tasks : [tasks.md](tasks.md)
- ADRs liés : [ADR-0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md) · [ADR-0002](../../adr/0002-cadrage-environnement-cible-google-cloud.md) · [ADR-0003](../../adr/0003-mvp-chargement-cypher-pur.md) · [ADR-0004](../../adr/0004-mvp-modele-espece-formes.md)
