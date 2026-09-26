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

## Lancer

```bash
pytest                    # tous les tests
pytest tests/unit/        # juste unit
pytest -m "not slow"      # skip les lents
pytest --cov --cov-report=html
```
