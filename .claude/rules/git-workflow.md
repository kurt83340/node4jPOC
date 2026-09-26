# Git workflow

## Commits — Conventional Commits

Format : `<type>(<scope>): <description>`

Types :

- `feat` : nouvelle feature
- `fix` : bug fix
- `docs` : doc uniquement
- `refactor` : refacto sans changement comportement
- `test` : ajout/modif tests
- `chore` : tooling, deps, config
- `perf` : amélioration perf

Exemples :

```
feat(api): add service-layer client for the external API
fix(client): handle 429 rate limit with exponential backoff
docs(runbook): add rollback procedure
```

## Branches

- `main` : prod-ready, protégée
- `feature/00X-nom-court` : 1 spec = 1 branche (mapping `specs/00X-*`)
- `fix/description-courte` : bug fixes
- `hotfix/description` : urgences prod (merge direct dans main + tag)

## PR / merge

- 1 spec terminée = 1 PR
- Squash merge (1 commit par feature dans main)
- Description PR : lien vers `specs/00X-*/spec.md`
- CI verte obligatoire (tests + lint + type check) — si le projet a une CI

## Tags

- Tag sur main après chaque déploiement prod : `vYYYY.MM.DD-HHMM`
- Pas de SemVer (projet client, pas une lib)

## Interdictions

- ❌ Force push sur main (jamais)
- ❌ Commit direct sur main (toujours PR)
- ❌ Skip CI hooks (`--no-verify`) — si ça casse, fixer le hook
- ❌ Credentials commitées — garde-fou gitleaks en pre-commit (`.pre-commit-config.yaml`,
  à activer par clone : `pre-commit install`) ; `git add` sur des chemins explicites, jamais `git add .` à l'aveugle
