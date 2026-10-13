# Architecture Decision Records (ADR)

> Décisions techniques **structurantes** du projet, capturées au fil du temps.
> **Immuables** : on ne modifie jamais un ADR existant. Si la décision change, on en crée un nouveau qui **supersede** l'ancien.
> Seule exception : le bandeau daté d'un amendement partiel (voir « Amendement partiel », en bas).

## Convention

- **Naming** : `00XX-<scope>-<titre-court>.md` (séquentiel, scope dans le nom)
- **Frontmatter YAML** obligatoire (status, scope, phase, supersedes)
- **5 scopes possibles** :
  - `cadrage` — contraintes capturées au début (souvent imposées par le client)
  - `mvp` — décisions structurantes au niveau projet entier
  - `feature-00X` — décisions **réutilisables** spécifiques à une feature
  - `infra` — hébergement, déploiement, secrets, monitoring
  - `operations` — décisions post-prod (incidents, runbook, ops)

## Index par scope

### 📥 cadrage — Contraintes client

| #                                                        | Titre                                            | Statut   |
| -------------------------------------------------------- | ------------------------------------------------ | -------- |
| [0002](0002-cadrage-environnement-cible-google-cloud.md) | Environnement cible : Google Cloud, dbt hors POC | Accepted |

### 🎨 mvp — Décisions projet structurantes

| #                                                    | Titre                                                                                             | Statut                                                                                                                                                           |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [0001](0001-mvp-jeu-de-donnees-pokeapi.md)           | Jeu de données : Pokémon (CSV PokéAPI, en français)                                               | Accepted                                                                                                                                                         |
| [0003](0003-mvp-chargement-cypher-pur.md)            | Chargement des données : Cypher pur (`LOAD CSV`)                                                  | Accepted                                                                                                                                                         |
| [0004](0004-mvp-modele-espece-formes.md)             | Modèle du graphe : espèce + toutes les formes                                                     | Accepted                                                                                                                                                         |
| [0005](0005-mvp-conventions-nommage-schema.md)       | Conventions de nommage du schéma                                                                  | Accepted                                                                                                                                                         |
| [0006](0006-mvp-banc-essai-30-questions.md)          | Banc d'essai : 30 questions de référence en 6 catégories                                          | Accepted                                                                                                                                                         |
| [0008](0008-mvp-notation-questions-semantiques.md)   | Notation des questions sémantiques : grille, trois ensembles, cœur de la question                 | Accepted                                                                                                                                                         |
| [0009](0009-mvp-protocole-mesure-techniques.md)      | Protocole de mesure des techniques du banc d'essai                                                | Accepted (points amendés par [0011](0011-infra-claude-par-api-anthropic.md), [0014](0014-mvp-revue-assistee.md) et [0015](0015-mvp-source-du-tour-precedent.md)) |
| [0012](0012-mvp-second-tour-apres-echec.md)          | Second tour d'une paire après un échec : faux d'office                                            | Accepted                                                                                                                                                         |
| [0014](0014-mvp-revue-assistee.md)                   | Revue assistée : pré-analyse de Claude, décision de Julien, contre-épreuve                        | Accepted                                                                                                                                                         |
| [0015](0015-mvp-source-du-tour-precedent.md)         | Source d'un second tour : une requête du tour précédent compte                                    | Accepted                                                                                                                                                         |
| [0017](0017-mvp-precisions-protocole-mesure.md)      | Précisions du protocole : plafonds invisibles, instructions du serveur ôtées, garde-fou, reprises | Accepted                                                                                                                                                         |
| [0018](0018-mvp-technique-sans-outil.md)             | Technique sans outil : consigne de contexte, source citée, encodage de la question                | Accepted                                                                                                                                                         |
| [0020](0020-mvp-index-vectoriel-des-descriptions.md) | Index vectoriel des descriptions : `gemini-embedding-001`, 3 072 dimensions, encodé par le plugin | Accepted                                                                                                                                                         |

### 🔧 features — Décisions promues depuis specs

| #                         | Titre | Statut |
| ------------------------- | ----- | ------ |
| _(aucune pour l'instant)_ |       |        |

### 🚀 infra — Hébergement & deploy

| #                                                   | Titre                                                                                 | Statut                                                                          |
| --------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| [0007](0007-infra-secrets-et-services-geres.md)     | Secrets dans Secret Manager, services gérés, poste local client                       | Accepted                                                                        |
| [0010](0010-infra-plafond-de-depense.md)            | Plafond de dépense : budget de 100 € et coupure automatique de Vertex                 | Accepted (point amendé par [0013](0013-infra-plafond-natif-de-vertex.md))       |
| [0011](0011-infra-claude-par-api-anthropic.md)      | Claude par l'API Anthropic, plafonné par des crédits prépayés                         | Accepted (point amendé par [0016](0016-infra-limite-anthropic-organisation.md)) |
| [0013](0013-infra-plafond-natif-de-vertex.md)       | Plafond natif mensuel de Vertex, en plus de la coupure de l'option C                  | Accepted                                                                        |
| [0016](0016-infra-limite-anthropic-organisation.md) | Clé Anthropic dans « Default », bornée par la limite de l'organisation                | Accepted                                                                        |
| [0019](0019-infra-jeton-vertex-du-plugin-genai.md)  | Jeton Vertex remis au plugin GenAI : compte de service limité à la prédiction, 15 min | Accepted                                                                        |

### 🛠️ operations — Post-prod & incidents

| #                     | Titre | Statut |
| --------------------- | ----- | ------ |
| _(à venir post-prod)_ |       |        |

### 🗄️ archived / superseded

_Chronologie des décisions remplacées :_

| # → #                     | Pourquoi | Date |
| ------------------------- | -------- | ---- |
| _(aucune pour l'instant)_ |          |      |

---

## Quand créer un ADR ?

✅ **OUI** :

- Choix de stack (langage, framework, BDD, orchestration)
- Choix d'archi (monolithe vs micro-services, REST vs GraphQL)
- Conventions structurantes (auth JWT vs sessions, async via Celery)
- Décisions de sécurité (où stocker les secrets)
- Migration de schéma BDD majeure
- **Cross-feature** : impacte plusieurs features

❌ **NON — utiliser une section `## Décisions` dans `plan.md` de la spec** :

- Choix de lib pour parser un CSV dans UNE feature
- Convention de nommage locale à une feature
- Refacto interne d'un module
- Fix de bug

**Règle de promotion** : si une décision de feature **survit à la feature** OU est **référencée par d'autres specs** → promouvoir en ADR global.

## Format d'un ADR

```markdown
---
status: accepted # proposed | accepted | deprecated | superseded
scope: mvp # cadrage | mvp | feature-00X | infra | operations
phase: 2026-Q2 # période / version où la décision a été prise
supersedes: null # ou 0003 si remplace une ADR existante
---

# 00XX — Titre court

**Statut :** Accepted
**Date :** YYYY-MM-DD
**Décideur :** Nom

## Contexte

[Pourquoi cette décision arrive, contraintes]

## Options considérées

- Option A : pros / cons / effort
- Option B : pros / cons / effort
- Option C : pros / cons / effort

## Décision

[Ce qu'on retient + raison principale]

## Conséquences

- ✅ Avantages
- ⚠️ Inconvénients / risques

## Liens

- [spec/feature concernée]
- [doc externe pertinente]
```

## Changement d'avis (supersede pattern)

Si on change d'avis (pivot, nouvelle contrainte, expérience) :

1. **Ne PAS modifier** l'ADR initial — il reste l'historique de ce qu'on pensait à l'époque
2. **Créer un nouveau ADR** avec frontmatter `supersedes: 00XX`
3. **Update le frontmatter de l'ancien** : `status: superseded` + `superseded_by: <nouveau>`
4. **Update CE README** : déplacer l'ancien ADR vers la section "archived / superseded" avec lien vers le nouveau

## Amendement partiel (pratique du projet depuis le 2026-10-08)

Quand un nouvel ADR ne remplace qu'un point d'un ADR qui reste en vigueur :

1. **Créer le nouvel ADR** avec `amends: 00XX` dans son frontmatter (`supersedes` reste `null`).
2. **Dans l'ancien, un seul ajout** : un bandeau daté en tête, qui nomme le point remplacé et renvoie au nouvel ADR ; rien d'autre ne change, il reste `accepted`.
3. **Dans cet index**, la ligne de l'ancien devient « Accepted (point amendé par NNNN) ».

Exemple : [0011](0011-infra-claude-par-api-anthropic.md) amende [0009](0009-mvp-protocole-mesure-techniques.md) (Claude par l'API Anthropic au lieu de Vertex) ; le reste du protocole de 0009 tient.
