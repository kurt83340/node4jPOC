---
paths: "**/*.py"
---

# Code style — Python

## Outils

- Formatter : `ruff format` · Linter : `ruff check --fix` · Types : `mypy` (`--strict` sur le code neuf)
- Avant commit : ces 3 commandes (ou leurs hooks, si le projet les a ajoutés à `.pre-commit-config.yaml`)

## Conventions

- Python 3.12+, type hints obligatoires (signatures publiques)
- Imports : isort via ruff
- Docstrings : Google style, uniquement sur fonctions publiques
- Longueur ligne : 100 chars
- f-strings > `.format()` > `%`

## Naming

- `snake_case` pour variables/fonctions
- `PascalCase` pour classes
- `UPPER_CASE` pour constantes module
- Pas de préfixe `_` sauf vraie privacy (rare)

## Erreurs

- Exceptions métier custom nommées par domaine (ex. `PaymentError`, `SyncError`) — jamais `Exception` générique levée
- JAMAIS de `except Exception:` nu — toujours typer
- Logs structurés via la lib de logging du projet (ex. `structlog`), pas de `print` dans le code livré
