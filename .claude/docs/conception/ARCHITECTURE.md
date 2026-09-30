# Architecture — node4jPOC v1.0

> 🛠️ **Pour qui** : Julien, et les agents du banc d'essai (ce modèle est ce qu'ils interrogent)
> 📋 **Ce fichier dit** : le **COMMENT technique** (composants, stack, modules, flux de données, sécurité, observabilité)
> ❌ **Ne contient PAS** : vision, périmètre, métriques → [cadrage](../cadrage/README.md) et [PRD.md](PRD.md)

**Statut :** Validée par Julien le 2026-09-29 (modèle v2, tâche T1.2 de la spec 001)
**Dernière MAJ :** 2026-10-01

## 1. Vue d'ensemble

### Composants techniques

```
┌──────────────────────────┐  https, LOAD CSV   ┌──────────────────────────┐
│ CSV PokéAPI (GitHub)     │ ─────────────────► │ AuraDB Free (Google      │
│ commit figé 168b1e8      │   côté serveur     │ Cloud), Cypher 25        │
└──────────────────────────┘                    └────────────▲─────────────┘
┌──────────────────────────┐  cypher-shell (Secret Manager) │
│ scripts/charger.sh       │ ───────────────────────────────┤
│ scripts/verifier.sh      │                                │
└──────────────────────────┘                                │
┌──────────────────────────┐  Query API, RETURN 1 par jour  │
│ infra/reveil-aura/       │ ───────────────────────────────┤
│ (Cloud Run, Scheduler)   │                                │ interrogé par
└──────────────────────────┘                                │
        Cypher à la main (jalon 1) · agents MCP, ADK (jalon 2) · GraphRAG (jalon 3)
        Aura Agent, Gemini Enterprise (jalon 4) · mémoire d'agent (jalon 5)
```

### Modèle du graphe (v2)

```
                   (:Pokemon)──EVOLUE_EN──►(:Pokemon)
                    │  ▲   │
  A_POUR_FORME_     │  │   └──A_POUR_DESCRIPTION──►(:Description)
  PAR_DEFAUT        ▼  │ FORME_DE
(:Talent)◄──A_LE_TALENT──(:Forme)──APPREND──►(:Attaque)
                          │                     │
               A_LE_TYPE  │                     │ A_LE_TYPE
                          ▼                     ▼
                        (:Type)◄───────────────┘
                          │ ▲
                          └─┘ SUPER_EFFICACE_CONTRE · PEU_EFFICACE_CONTRE · SANS_EFFET_CONTRE
```

Deux niveaux ([ADR-0004](../adr/0004-mvp-modele-espece-formes.md)) : le **Pokémon** (niveau espèce) porte l'identité (nom, catégorie, descriptions, évolutions) ; la **forme** porte ce qui varie (types, stats, talents, attaques). « Dracaufeu » est un `Pokemon` ; Méga-Dracaufeu X en est une `Forme`. Chaque Pokémon a une forme par défaut, visible deux fois dans le schéma : la relation `A_POUR_FORME_PAR_DEFAUT` et la propriété `parDefaut`. Conventions de nommage : [ADR-0005](../adr/0005-mvp-conventions-nommage-schema.md).

### Séquence d'un chargement

```
scripts/charger.sh
     ├─► 00 contraintes et index
     ├─► 01 types et efficacités
     ├─► 02 Pokémon, puis EVOLUE_EN (seconde passe)
     ├─► 03 formes, FORME_DE, A_POUR_FORME_PAR_DEFAUT, stats, A_LE_TYPE
     ├─► 04 talents, A_LE_TALENT
     ├─► 05 attaques, leur type, APPREND (en lots)
     └─► 06 descriptions
scripts/verifier.sh : comptes, empreintes, doublons, limite de l'instance
```

## 2. Stack technique (vue archi)

Stack résumé des choix **structurants** avec ADR liés.
→ **Inventaire complet** (libs + services tiers + LLM + deploy) : [../stack.md](../stack.md)

| Couche                  | Choix                                       | Justification                                               | ADR                                                             |
| ----------------------- | ------------------------------------------- | ----------------------------------------------------------- | --------------------------------------------------------------- |
| Données                 | **PokéAPI, CSV au commit `168b1e8`**        | textes en français, graphe naturel, réponses vérifiables    | [0001](../adr/0001-mvp-jeu-de-donnees-pokeapi.md)               |
| Environnement cible     | **Google Cloud** (dbt hors POC)             | transposable à l'entreprise de Julien                       | [0002](../adr/0002-cadrage-environnement-cible-google-cloud.md) |
| Base de données         | **AuraDB Free**, Cypher 25 par défaut       | gratuite, hébergée sur Google Cloud, requise par Aura Agent | [0002](../adr/0002-cadrage-environnement-cible-google-cloud.md) |
| Chargement              | **Cypher pur** (`LOAD CSV`, `cypher-shell`) | pratiquer le Cypher de chargement                           | [0003](../adr/0003-mvp-chargement-cypher-pur.md)                |
| Modèle                  | **Pokémon (espèce) + toutes les formes**    | fidèle à la source ; identité et variantes                  | [0004](../adr/0004-mvp-modele-espece-formes.md)                 |
| Nommage du schéma       | **conventions Neo4j, mots des questions**   | c'est tout ce que voit un agent text-to-Cypher              | [0005](../adr/0005-mvp-conventions-nommage-schema.md)           |
| LLM, embeddings, agents | à décider aux jalons 2 à 4                  | —                                                           | —                                                               |

## 3. Modules & découpage

- **Chargement** (`cypher/`) : un fichier `.cypher` par groupe de données, idempotent, exécuté dans l'ordre.
- **Outillage** (`scripts/`) : chargement, purge, vérification, rejeu des questions ; avec le job ci-dessous, seul endroit qui lit les identifiants.
- **Exploitation** (`infra/reveil-aura/`) : job Cloud Run lancé chaque jour par Cloud Scheduler, qui garde l'instance Free éveillée et alerte par e-mail en cas d'échec ; déployé par `deploy.sh`, exploité avec le [RUNBOOK](../RUNBOOK.md).
- **Banc d'essai** (`questions/`) : les 30 questions, leurs requêtes de référence et leurs réponses attendues ; commun à tous les jalons.

> ⚠️ Ce qui **n'est PAS déductible du code** — règles de couplage, intention, gotchas — vit dans **[../code-map.md](../code-map.md)** (auto-chargé ; ses gotchas, dans `code-map-gotchas.md`, sont injectés par hook à l'édition du fichier ciblé). Ne pas le dupliquer ici.

## 4. Flux de données

1. **Lecture** : Aura lit chaque CSV en https depuis le commit figé (`$base` en paramètre) ; tout arrive en chaîne de caractères, converti au chargement.
2. **Écriture** : `MERGE` sur une clé contrainte (ou sur un chemin pour `Description`), en lots pour les gros fichiers. Détail et cas limites : [plan de la spec 001](../specs/001-socle-donnees/plan.md).
3. **Contrôle** : `verifier.sh` compare la base aux comptes et empreintes attendus.
4. **Usage** : les techniques du banc d'essai lisent la base, le job `reveil-aura` y lit `RETURN 1` chaque jour ; seul le chargement y écrit (et la mémoire d'agent, au jalon 5).

## 5. Mapping champs (si applicable)

Chaque élément du modèle sert au moins une des [30 questions](../../../questions/README.md) ; ce qu'aucune question ne demande n'est pas chargé (plan, D10). Propriétés en camelCase, identifiants sans accents ([ADR-0005](../adr/0005-mvp-conventions-nommage-schema.md)).

### Nœuds

| Label                 | Propriétés                                                                                                                                          | Source (CSV)                                                             | Transformation                                                                                                                                    | Questions                                                                  |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `Pokemon` (1 025)     | `id`, `identifiantPokeapi`, `nom`, `categorie`                                                                                                      | `pokemon_species`, `pokemon_species_names` (langue 5 : `name`, `genus`)  | —                                                                                                                                                 | toutes (entrée par le nom) ; `categorie` : Q23                             |
| `Forme` (1 351)       | `id`, `identifiantPokeapi`, `nom`, `parDefaut`, `statPv`, `statAttaque`, `statDefense`, `statAttaqueSpeciale`, `statDefenseSpeciale`, `statVitesse` | `pokemon`, `pokemon_forms` + `pokemon_form_names` (nom), `pokemon_stats` | nom : celui du Pokémon pour la forme par défaut, sinon celui de sa `pokemon_form` par défaut, ou de l'unique ; les 6 stats pivotées en propriétés | toutes ; formes : Q6, Q12, Q15 ; stats : Q12, Q21                          |
| `Type` (18)           | `id`, `identifiantPokeapi`, `nom`                                                                                                                   | `types`, `type_names`                                                    | types 19, 10001 et 10002 (Stellaire, ???, Obscur) ignorés                                                                                         | Q1, Q2, Q4, Q6, Q7, Q9, Q11, Q13, Q14, Q17 à Q20, Q22, Q24, Q25, Q27 à Q29 |
| `Attaque` (919)       | `id`, `identifiantPokeapi`, `nom`, `puissance`, `precision`, `pp`, `categorie`                                                                      | `moves`, `move_names`, `move_damage_class_prose`                         | les 18 attaques Obscur exclues ; valeur vide → propriété absente                                                                                  | Q1, Q7, Q8, Q13, Q14, Q20, Q24, Q27, Q28, Q30                              |
| `Talent` (313)        | `id`, `identifiantPokeapi`, `nom`                                                                                                                   | `abilities`, `ability_names`                                             | seulement les talents utilisés ; nom FR, sinon identifiant (3 talents récents)                                                                    | Q4 (Q7 en bonus)                                                           |
| `Description` (5 233) | `texte`, `jeux`                                                                                                                                     | `pokemon_species_flavor_text` (langue 5), `versions`, `version_names`    | `\n` et U+202F → espace, puis `trim` ; une par texte distinct et par Pokémon ; pas de clé étrangère ; `jeux` = provenance, pour citer ses sources | Q3, Q9, Q16, Q17, Q26                                                      |

### Relations

| Relation                                                                                              | Propriétés                          | Source (CSV)                                                         | Transformation                                                                                                      | Questions                                                   |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `(:Forme)-[:FORME_DE]->(:Pokemon)` (1 351)                                                            | —                                   | `pokemon.species_id`                                                 | —                                                                                                                   | Q6, Q12, Q15                                                |
| `(:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)` (1 025)                                             | —                                   | `pokemon.is_default`                                                 | relation spécialisée, à côté de la générique `FORME_DE`                                                             | presque toutes (« Pokémon » = forme par défaut)             |
| `(:Pokemon)-[:EVOLUE_EN]->(:Pokemon)` (484)                                                           | —                                   | `pokemon_species.evolves_from_species_id`                            | seconde passe (17 sources après leur cible dans le CSV)                                                             | Q5, Q8 (famille), Q15                                       |
| `(:Forme)-[:A_LE_TYPE]->(:Type)` (2 116)                                                              | `rang` (1 = type principal)         | `pokemon_types`                                                      | —                                                                                                                   | Q1, Q2, Q4, Q6, Q7, Q9, Q11, Q14, Q17 à Q19, Q25, Q27 à Q29 |
| `(:Attaque)-[:A_LE_TYPE]->(:Type)` (919)                                                              | —                                   | `moves.type_id`                                                      | —                                                                                                                   | Q1, Q13, Q14, Q20, Q24, Q27, Q28                            |
| `(:Type)-[:SUPER_EFFICACE_CONTRE \| PEU_EFFICACE_CONTRE \| SANS_EFFET_CONTRE]->(:Type)` (51 + 61 + 8) | `facteur` décimal (2.0 ; 0.5 ; 0.0) | `type_efficacy`                                                      | 200 → super efficace, 50 → peu efficace, 0 → sans effet ; 100 (neutre) ignoré, il vaut ×1 dans un produit           | Q1, Q2, Q7, Q11, Q18, Q22, Q27, Q28                         |
| `(:Forme)-[:A_LE_TALENT]->(:Talent)` (2 943)                                                          | `cache`                             | `pokemon_abilities`                                                  | `trim` avant conversion (fins de ligne Windows)                                                                     | Q4                                                          |
| `(:Forme)-[:APPREND]->(:Attaque)` (99 509)                                                            | `methodes`, `niveau`                | `pokemon_moves`, `pokemon_move_method_prose`, `pokemon_move_methods` | agrégé par couple : union des méthodes (repli sur l'identifiant pour « train »), niveau minimal de montée de niveau | Q1, Q7, Q8, Q13, Q14, Q20, Q27, Q28                         |
| `(:Pokemon)-[:A_POUR_DESCRIPTION]->(:Description)` (5 233)                                            | —                                   | `pokemon_species_flavor_text`                                        | —                                                                                                                   | Q3, Q9, Q16, Q17, Q26                                       |

Total attendu : **8 859 nœuds et 113 700 relations**.

### Contraintes et index

- Une contrainte d'unicité sur `id` pour `Pokemon`, `Forme`, `Type`, `Attaque` et `Talent`. `Description` n'a pas de clé : un `MERGE` sur le chemin (Pokémon, texte) la rend unique, et `verifier.sh` le contrôle.
- Un index sur `nom` pour `Pokemon`, `Forme`, `Attaque`, `Talent` et `Type` : c'est la porte d'entrée de presque toutes les questions.

## 6. Sécurité

- Identifiants Aura dans Secret Manager (secret `neo4j-aura-poc`, [ADR-0007](../adr/0007-infra-secrets-et-services-geres.md)) : `charger.sh` les lit au lancement et n'en passe que 4 variables à `cypher-shell`, jamais affichées ni écrites sur le disque. Le fichier `Neo4j-*.txt` téléchargé depuis Aura ne fait que transiter : ignoré par git, interdit en lecture, supprimé après le dépôt.
- Les CSV ne sont ni copiés dans le dépôt ni republiés (univers Pokémon © Nintendo, [ADR-0001](../adr/0001-mvp-jeu-de-donnees-pokeapi.md)).
- Les techniques du banc d'essai lisent la base en lecture seule quand l'outil le permet (mode lecture seule de `neo4j/mcp`, par exemple).
- Le job `reveil-aura` lit le même secret, que Cloud Run monte en fichier, sous un compte de service qui ne peut que lire ce secret et lancer ce job ; il interroge Aura en lecture seule, et ses journaux ne contiennent ni le mot de passe ni l'identifiant de l'instance.

## 7. Observabilité

- **Chargement** : un journal horodaté par fichier `.cypher` (durée, lignes traitées).
- **Contrôle** : `verifier.sh` (comptes, empreintes, doublons, volume comparé à la limite de l'instance).
- **Supervision** : le job quotidien `reveil-aura` interroge Aura ; toute erreur du job ou de son déclencheur envoie un e-mail (alerte Cloud Monitoring sur journaux, [RUNBOOK](../RUNBOOK.md)). L'alerte ne voit pas l'absence d'exécution : planification coupée, plus d'e-mail. Rien d'autre : c'est un POC, relancé à la demande.

## 8. Évolutions prévues (v2+)

- **Jalon 2** :
  - une **fiche de schéma** commune à toutes les techniques (règles, valeurs possibles, 5 à 10 exemples), donnée à l'identique pour ne pas biaiser la comparaison : `get-schema` de `neo4j/mcp` ne transmet ni les règles ni les valeurs ;
  - une **mesure « schéma français contre anglais »** sur les 30 questions (effet jamais mesuré en text-to-Cypher) ;
  - un index plein texte sur les noms (recherche approchée, utile à Q19 « Dracofeu »).
- **Jalon 3** : index vectoriel sur `Description.texte`, avec `gemini-embedding-001` pour qu'un seul index serve aussi à Aura Agent (jalon 4). La fiche de schéma interdira de renvoyer des nœuds `Description` entiers (le vecteur remplirait la réponse).
- **Propriétés écartées faute de question** (à ajouter si une question en a besoin) : conditions d'évolution (`pokemon_evolution`), génération, légendaire, habitat, taille, poids.
- **Formes cosmétiques** (`pokemon_forms` sans stats propres, comme les 28 motifs de Zarbi) : non modélisées.
- **`Type`** est un mot-clé de Cypher, déconseillé comme label : testé au go/no-go (T2.2), renommé seulement si ça casse.
