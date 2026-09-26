# Architecture Decision Records (ADR)

> Décisions techniques **structurantes** du projet, capturées au fil du temps.
> **Immuables** : on ne modifie jamais un ADR existant. Si la décision change, on en crée un nouveau qui **supersede** l'ancien.

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

- _(aucune pour l'instant — les contraintes initiales sont capturées dans [../cadrage/README.md](../cadrage/README.md))_

### 🎨 mvp — Décisions projet structurantes

| #                                                                        | Titre | Statut |
| ------------------------------------------------------------------------ | ----- | ------ |
| _(aucune pour l'instant — créer dès la 1ère décision tech structurante)_ |       |        |

### 🔧 features — Décisions promues depuis specs

| #                         | Titre | Statut |
| ------------------------- | ----- | ------ |
| _(aucune pour l'instant)_ |       |        |

### 🚀 infra — Hébergement & deploy

| #                     | Titre | Statut |
| --------------------- | ----- | ------ |
| _(à venir post-prod)_ |       |        |

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
