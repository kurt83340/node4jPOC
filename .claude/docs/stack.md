# Stack — node4jPOC

> Généré depuis le template claude-Setup v1.5.0 le 2026-09-26

> **Catalogue technique pur** : langage, libs, services tiers, LLM, infra/deploy.
> Le **POURQUOI** des choix vit dans [adr/](adr/). L'**ARCHI** globale (dont **sécurité** & **observabilité**) dans [conception/ARCHITECTURE.md](conception/ARCHITECTURE.md) ; les **conventions de test** dans [../rules/testing.md](../rules/testing.md).
> Ce fichier = **vue catalogue rapide** ("quelles techs on utilise et pour quoi ?") — **pas** de narratif archi/sécurité/tests ici (sinon drift avec ARCHITECTURE).

**Dernière MAJ :** 2026-09-30

## Langage(s) & runtime

| Item           | Version | Notes                                                                                                        |
| -------------- | ------- | ------------------------------------------------------------------------------------------------------------ |
| Cypher         | 25      | langue par défaut de la base, à régler au go/no-go (T2.2, D7 du [plan 001](specs/001-socle-donnees/plan.md)) |
| Bash           | —       | scripts de chargement et de vérification (à venir)                                                           |
| Java (OpenJDK) | 21      | paquet `openjdk-21-jre` (apt), requis par `cypher-shell`                                                     |

## Orchestration

| Composant                  | Choix                                                                                                                         | Voir                                              |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| Chargement et vérification | **scripts bash** `scripts/charger.sh` et `scripts/verifier.sh` (à venir), qui passent les fichiers `cypher/` à `cypher-shell` | [ADR-0003](adr/0003-mvp-chargement-cypher-pur.md) |
| Agents (jalons 2 à 4)      | à choisir au démarrage du jalon 2                                                                                             | [ROADMAP](ROADMAP.md)                             |

## Stockage & data

| Source/Destination                              | Usage                                                                                | Voir                                                             |
| ----------------------------------------------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| **CSV PokéAPI** (GitHub, commit figé `168b1e8`) | lecture par `LOAD CSV`, exécuté côté Aura                                            | [ADR-0001](adr/0001-mvp-jeu-de-donnees-pokeapi.md)               |
| **Neo4j AuraDB Free** (sur Google Cloud)        | écrite par le chargement, lue par les techniques ; instance pas encore créée (NEO-6) | [ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md) |

## Librairies (rôles)

| Lib              | Version   | Pour quoi                                                               | Module qui l'utilise                                  |
| ---------------- | --------- | ----------------------------------------------------------------------- | ----------------------------------------------------- |
| `cypher-shell`   | 2026.09.0 | client Neo4j en ligne de commande (`.deb` officiel de dist.neo4j.org)   | `scripts/charger.sh`, `scripts/verifier.sh` (à venir) |
| _(aucune autre)_ | —         | bibliothèques des jalons 2 à 4 : à choisir au démarrage de chaque jalon | —                                                     |

## LLM providers (par feature)

| Feature                            | LLM utilisé | Coût estimé | Notes                             |
| ---------------------------------- | ----------- | ----------- | --------------------------------- |
| _(aucun usage LLM pour l'instant)_ | —           | —           | à choisir au démarrage du jalon 2 |

⚠️ **Si une feature utilise un LLM**, documenter ici **ET** dans `specs/00X-feature/plan.md` (section "LLM choisi + raison + coût estimé").

Options envisagées : voir le jalon 2 de la [ROADMAP](ROADMAP.md).

## Services tiers / SaaS

| Service                                               | Usage                                                                                            | Statut                        | Coût                                                     | Voir                                                             |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------- |
| **Google Cloud** (projet `jleroy-labo`)               | projet du POC : Secret Manager, puis les services des jalons 2 à 4                               | ✅ facturation active         | à l'usage                                                | [ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md) |
| **Google Secret Manager** (projet `jleroy-labo`)      | stockage des secrets, identifiants Aura compris                                                  | ⏳ à mettre en place au NEO-6 | gratuit sous 6 versions actives et 10 000 accès par mois | `ACCESS.md` _(à créer en T2.1)_                                  |
| **Jira Cloud** (projet NEO, Kanban géré par l'équipe) | suivi : un epic par jalon, un ticket par phase ; le dépôt fait foi                               | ✅ actif                      | gratuit (offre Free)                                     | [README](../../README.md)                                        |
| **GitHub** (dépôt privé `kurt83340/node4jPOC`)        | code et PR, fusionnées en squash dans `main`                                                     | ✅ actif                      | gratuit (offre Free)                                              | [git-workflow](../rules/git-workflow.md)                         |
| **GitHub for Atlassian**                              | relie le dépôt à NEO : une clé de ticket dans un commit ou un titre de PR remonte dans le ticket | ✅ actif                      | gratuit                                                             | [git-workflow](../rules/git-workflow.md)                         |

❌ **Pas utilisé** : dbt, Graph Data Science for BigQuery, Spanner Graph (voir « Hors POC » dans la [ROADMAP](ROADMAP.md)).

## Infra & Deploy

| Item        | Choix                                     | Notes                                                                                            |
| ----------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Hébergement | services gérés : Neo4j Aura, Google Cloud | le poste local n'est qu'un client, pas de VPS ; agents : à choisir au démarrage des jalons 2 à 4 |
| CI/CD       | aucune CI                                 | garde-fou local : gitleaks v8.30.1 en pre-commit (`pre-commit install` une fois par clone)       |
| Versioning  | Tags git `vYYYY.MM.DD-HHMM`               | Voir [git-workflow.md](../rules/git-workflow.md)                                                 |

## Hors de ce catalogue (home unique — ne pas dupliquer ici)

Pour éviter le drift, ces aspects vivent **ailleurs** (ce fichier ne fait que pointer) :

- **Auth & sécurité** (patterns auth, secrets storage, anti-patterns credentials) → [conception/ARCHITECTURE.md](conception/ARCHITECTURE.md) §6 Sécurité
- **Monitoring & observabilité** (logs, metrics, alerting, rétention) → [conception/ARCHITECTURE.md](conception/ARCHITECTURE.md) §7 Observabilité
- **Tests** (frameworks, couverture, commandes) → [../rules/testing.md](../rules/testing.md)

## Évolutions stack prévues (v2+)

- Jalons 2 à 4 : `neo4j/mcp`, agent ADK, embeddings Gemini, Aura Agent, Agent Runtime ; outils et versions à choisir au démarrage de chaque jalon ([ROADMAP](ROADMAP.md), [ARCHITECTURE](conception/ARCHITECTURE.md) § 8)
- Jalons 5 et 6, en option : voir la [ROADMAP](ROADMAP.md)

## Mise à jour

- **Nouvelle lib ajoutée** : update la table "Librairies"
- **Nouveau service SaaS** : update "Services tiers"
- **Feature ajoute usage LLM** : update "LLM providers" + référencer dans specs/00X/plan.md
- **Changement infra** : update "Infra & Deploy"
- **Source of truth** : `.pre-commit-config.yaml` (gitleaks) et `cypher-shell --version` pour les versions exactes (pas encore de `pyproject.toml` ni de `package.json`), CE fichier pour le contexte humain (WHY + services tiers + LLM)
