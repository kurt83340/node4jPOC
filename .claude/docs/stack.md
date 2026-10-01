# Stack — node4jPOC

> Généré depuis le template claude-Setup v1.5.0 le 2026-09-26

> **Catalogue technique pur** : langage, libs, services tiers, LLM, infra/deploy.
> Le **POURQUOI** des choix vit dans [adr/](adr/). L'**ARCHI** globale (dont **sécurité** & **observabilité**) dans [conception/ARCHITECTURE.md](conception/ARCHITECTURE.md) ; les **conventions de test** dans [../rules/testing.md](../rules/testing.md).
> Ce fichier = **vue catalogue rapide** ("quelles techs on utilise et pour quoi ?") — **pas** de narratif archi/sécurité/tests ici (sinon drift avec ARCHITECTURE).

**Dernière MAJ :** 2026-09-30

## Langage(s) & runtime

| Item           | Version | Notes                                                                                                                                                                                                            |
| -------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cypher         | 25      | déjà la langue par défaut de la base, contrôlé au go/no-go (T2.2, D7 du [plan 001](specs/001-socle-donnees/plan.md))                                                                                             |
| Bash           | —       | `scripts/charger.sh` (`--tout`, `--idempotence`, `--ping`, `--go-no-go`, `--purge`), `scripts/verifier.sh`, `scripts/questions.sh` (`--verifier`, `--enregistrer`), fonctions partagées dans `scripts/commun.sh` |
| Java (OpenJDK) | 21      | paquet `openjdk-21-jre` (apt), requis par `cypher-shell`                                                                                                                                                         |
| Python         | 3.14    | `infra/reveil-aura/reveil.py`, bibliothèque standard seule ; image `python:3.14-slim`                                                                                                                            |

## Orchestration

| Composant                  | Choix                                                                                                               | Voir                                              |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| Chargement et vérification | **scripts bash** `scripts/charger.sh` et `scripts/verifier.sh`, qui passent les fichiers `cypher/` à `cypher-shell` | [ADR-0003](adr/0003-mvp-chargement-cypher-pur.md) |
| Agents (jalons 2 à 4)      | à choisir au démarrage du jalon 2                                                                                   | [ROADMAP](ROADMAP.md)                             |

## Stockage & data

| Source/Destination                              | Usage                                                                                                                                            | Voir                                                             |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| **CSV PokéAPI** (GitHub, commit figé `168b1e8`) | lecture par `LOAD CSV`, exécuté côté Aura                                                                                                        | [ADR-0001](adr/0001-mvp-jeu-de-donnees-pokeapi.md)               |
| **Neo4j AuraDB Free** (sur Google Cloud)        | écrite par le chargement, lue par les techniques ; instance créée le 2026-09-30 (GCP `europe-west1`, au plus 200 000 nœuds et 400 000 relations) | [ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md) |

## Librairies (rôles)

| Lib                            | Version                     | Pour quoi                                                                                                                                                                                          | Module qui l'utilise                                |
| ------------------------------ | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `cypher-shell`                 | 2026.09.0                   | client Neo4j en ligne de commande (`.deb` officiel de dist.neo4j.org)                                                                                                                              | `scripts/charger.sh`, `scripts/verifier.sh`         |
| `gcloud` (Google Cloud SDK)    | 587.0.0                     | lecture du secret `neo4j-aura-poc` dans Secret Manager ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md)) ; déploiement du job `reveil-aura`, avec le composant `beta` pour le canal e-mail | `scripts/charger.sh`, `infra/reveil-aura/deploy.sh` |
| pytest, pytest-cov, ruff, mypy | 9.1.1, 7.1.0, 0.16.9, 2.3.1 | tests et contrôles du job `reveil-aura` (groupe `dev`, figé par `uv.lock`)                                                                                                                         | `infra/reveil-aura/`                                |
| _(aucune autre)_               | —                           | bibliothèques des jalons 2 à 4 : à choisir au démarrage de chaque jalon                                                                                                                            | —                                                   |

## LLM providers (par feature)

| Feature                            | LLM utilisé | Coût estimé | Notes                             |
| ---------------------------------- | ----------- | ----------- | --------------------------------- |
| _(aucun usage LLM pour l'instant)_ | —           | —           | à choisir au démarrage du jalon 2 |

⚠️ **Si une feature utilise un LLM**, documenter ici **ET** dans `specs/00X-feature/plan.md` (section "LLM choisi + raison + coût estimé").

Options envisagées : voir le jalon 2 de la [ROADMAP](ROADMAP.md).

## Services tiers / SaaS

| Service                                                     | Usage                                                                                            | Statut                   | Coût                                                                                                                                       | Voir                                                                          |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| **Google Cloud** (projet `jleroy-labo`)                     | projet du POC : Secret Manager, puis les services des jalons 2 à 4                               | ✅ facturation active    | à l'usage                                                                                                                                  | [ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md)              |
| **Google Secret Manager** (projet `jleroy-labo`)            | stockage des secrets, identifiants Aura compris                                                  | ✅ en place (2026-09-30) | gratuit sous 6 versions actives et 10 000 accès par mois                                                                                   | [ACCESS](ACCESS.md) · [ADR-0007](adr/0007-infra-secrets-et-services-geres.md) |
| **Cloud Scheduler et Cloud Run** (projet `jleroy-labo`)     | job `reveil-aura` : un `RETURN 1` par jour, pour que l'instance Free ne se mette pas en pause    | ✅ en place (2026-09-30) | gratuit : 1 des 3 jobs Scheduler offerts par compte de facturation ; environ 1 900 vCPU-s par mois sur les 240 000 offerts                 | [RUNBOOK](RUNBOOK.md)                                                         |
| **Cloud Monitoring** (projet `jleroy-labo`)                 | alerte par e-mail quand le job échoue (condition de journaux)                                    | ✅ en place (2026-09-30) | gratuit aujourd'hui ; 0,35 $ par mois pour cette alerte au plus tôt à partir du 2027-09-01, annoncé 90 et 30 jours avant                   | [RUNBOOK](RUNBOOK.md)                                                         |
| **Cloud Build et Artifact Registry** (projet `jleroy-labo`) | construction et stockage de l'image du job `reveil-aura` (`gcloud run jobs deploy --source`)     | ✅ en place (2026-09-30) | gratuit : 2 500 minutes de build et 0,5 Gio d'images par mois (2 images gardées) ; bucket des sources à Paris : quelques Ko, sans gratuité | [ACCESS](ACCESS.md)                                                           |
| **Jira Cloud** (projet NEO, Kanban géré par l'équipe)       | suivi : un epic par jalon, un ticket par phase ; le dépôt fait foi                               | ✅ actif                 | gratuit (offre Free)                                                                                                                       | [README](../../README.md)                                                     |
| **GitHub** (dépôt privé `kurt83340/node4jPOC`)              | code et PR, fusionnées en squash dans `main`                                                     | ✅ actif                 | gratuit (offre Free)                                                                                                                       | [git-workflow](../rules/git-workflow.md)                                      |
| **GitHub for Atlassian**                                    | relie le dépôt à NEO : une clé de ticket dans un commit ou un titre de PR remonte dans le ticket | ✅ actif                 | gratuit                                                                                                                                    | [git-workflow](../rules/git-workflow.md)                                      |

❌ **Pas utilisé** : dbt, Graph Data Science for BigQuery, Spanner Graph (voir « Hors POC » dans la [ROADMAP](ROADMAP.md)).

## Infra & Deploy

| Item        | Choix                                                   | Notes                                                                                                                                                                                               |
| ----------- | ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hébergement | services gérés : Neo4j Aura, Google Cloud               | le poste local n'est qu'un client : ni VPS ni Docker ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md)) ; job `reveil-aura` sur Cloud Run ; agents : à choisir au démarrage des jalons 2 à 4 |
| Déploiement | `infra/reveil-aura/deploy.sh` (gcloud), lancé à la main | image construite par Cloud Build depuis le `Dockerfile` ; procédures : [RUNBOOK](RUNBOOK.md)                                                                                                        |
| CI/CD       | aucune CI                                               | garde-fou local : gitleaks v8.30.1 en pre-commit (`pre-commit install` une fois par clone)                                                                                                          |
| Versioning  | Tags git `vYYYY.MM.DD-HHMM`                             | Voir [git-workflow.md](../rules/git-workflow.md)                                                                                                                                                    |

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
- **Source of truth** : `.pre-commit-config.yaml` (gitleaks), `cypher-shell --version` et `infra/reveil-aura/pyproject.toml` (avec son `uv.lock`) pour les versions exactes, CE fichier pour le contexte humain (WHY + services tiers + LLM)
