---
paths: "**/*.py"
---

# Testing — Python

## Outils

- Framework : `pytest` · Coverage : `pytest-cov` (objectif **80 %** sur le code métier)
- Fixtures : `tests/fixtures/`
- Mocks HTTP : la lib dédiée au client utilisé (ex. `respx` pour httpx, `responses` pour requests), pas `unittest.mock` brut

## Structure

```
tests/
├── unit/          # rapides, sans I/O
├── integration/   # vraies dépendances (BDD jetable en conteneur, ex. testcontainers)
├── e2e/           # parcours complet (lents, peu nombreux)
└── fixtures/      # réponses d'API enregistrées, jeux de données
```

## Règles

- Test = miroir du module (`src/<pkg>/client.py` → `tests/unit/test_client.py`)
- 1 test = 1 comportement (assertion principale lisible)
- Pas de mock de la BDD en intégration → vraie BDD jetable
- Pas d'appel réseau réel en CI (mocks HTTP)
- Suite verte avant push

## Tests d'exclusion (refus, erreur ou « à revoir » attendus)

Leçon du 2026-10-08, constatée trois fois ([lecons.md](../docs/lecons.md)) : un tel test passe souvent pour une autre raison
que la règle qu'il vise, et survit alors à sa suppression.

- Son entrée est acceptée par toutes les autres règles : seule la règle visée la refuse.
- Le message attendu (`match=`) est propre à la règle visée, jamais un fragment que celui d'une règle voisine contient.
- Une borne se teste pile dessus (`<` contre `<=`).
- Vérification par mutation : désactiver la seule règle visée doit faire échouer son test.

## Client tiers : le vrai, contre de faux services

Leçon du 2026-10-09, servie trois fois (spec 002 : T4.1, T4.2, T4.3 ; [lecons.md](../docs/lecons.md)) : la doc d'un client
tiers (CLI, SDK, framework d'agents) tait des comportements que le code doit connaître.

- Avant d'en dépendre, lancer le vrai client, à sa version figée, contre de faux services locaux (fausse API, faux
  serveur MCP, ADC factice) : aucun appel réel, aucune connexion hors des faux.
- Relever ce qu'il envoie et ce qu'il fait (requêtes, variables lues, fichiers et sockets ouverts, reprises), puis le
  garder en test.

## Lancer

```bash
uv run --directory banc pytest -q                 # harnais : banc/tests/, à plat
uv run --directory infra/reveil-aura pytest -q    # de même pour infra/coupure-vertex
```
