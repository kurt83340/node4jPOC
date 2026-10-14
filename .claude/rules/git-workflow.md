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

**Clé Jira** : un commit qui fait avancer un ticket du projet NEO cite sa clé à la fin du sujet, entre
parenthèses : `feat(chargement): charger les 18 types (NEO-9)`. GitHub for Atlassian affiche alors le
commit dans le ticket. Les Smart Commits (`#done`, `#comment`) ne marchent pas ici : l'e-mail des
commits n'est pas celui du compte Jira.

## Branches

- `main` : prod-ready, protégée
- `feature/00X-phase-N` : une branche par phase de `specs/00X-*/tasks.md`, tirée de `main` à jour, vivante quelques
  heures ; la conception d'une spec est sa première phase (`feature/00X-conception`)
- `fix/description-courte` : bug fixes
- `chore/description-courte` : outillage du dépôt hors spec (CI, dépendances), avec son ticket
- `hotfix/description` : urgences prod (merge direct dans main + tag)
- Pas de clé Jira dans le nom d'une branche : elle va dans les commits et dans le titre de la PR

## PR / merge

- 1 phase = 1 PR, courte : la conception ouvre la spec, `/feature-done` ouvre la dernière (ROADMAP, CHANGELOG, tag)
- **Merge commit**, jamais squash ni rebase (seul mode permis par le dépôt) : tous les commits restent dans `main`,
  et `git log --first-parent main` en donne le résumé, une ligne par PR
- Avant la PR : `git merge main` dans la branche si `main` a bougé ; des commits propres (Conventional Commits,
  clé NEO, pas de « wip »)
- Description PR : lien vers `specs/00X-*/spec.md` et vers la phase de `tasks.md`
- Titre de PR : il finit par la clé du ticket de la phase, par exemple `(NEO-15)`, enfant de l'epic du jalon ; si la
  phase relève de deux tickets, les deux : `(NEO-15, NEO-16)`. La PR
  de conception porte la clé de l'epic, par exemple `(NEO-2)`. Le commit de fusion reprend ce titre (réglage du dépôt)
- Branche supprimée à la fusion (réglage du dépôt) : ses commits restent dans `main`
- CI verte obligatoire (`.github/workflows/ci.yml` : tests, lint, types, shell, format, secrets) : `gh pr checks <n>`
  tout vert avant `gh pr merge`. GitHub Free et dépôt privé : aucune protection de branche, rien d'autre ne bloque
  la fusion d'une PR rouge
- Ticket Jira de la phase : « En cours » dès sa première tâche ; à la fusion de sa PR, son format de clôture (« À faire »
  cochés, « Résultats du AAAA-MM-JJ », PR en lien intelligent avec son état) est montré à Julien, puis publié ; « Terminé »
  seulement après sa relecture (`--relu` du skill jira). Leçon du 2026-10-11 ([lecons.md](../docs/lecons.md))
- Fin de session : `/handoff` sur la branche de la dernière phase, avant la fusion de sa PR : le HANDOFF
  auto-chargé est celui de `main`. Si tout est déjà fusionné, une petite PR doc pour lui (« docs(00X): handoff du
  AAAA-MM-JJ (NEO-NN) »), comme la n°24 le 2026-10-13

## Tags

- Tag annoté `jalon-N` sur `main` quand un jalon est livré (`/feature-done`) :
  `git log --first-parent jalon-1..jalon-2` liste ce que le jalon 2 a livré
- Tag sur main après chaque déploiement prod : `vYYYY.MM.DD-HHMM`
- Pas de SemVer (projet client, pas une lib)

## Interdictions

- ❌ Force push sur main (jamais)
- ❌ Attribution à Claude dans un commit ou une PR (`Co-Authored-By`, « Generated with Claude Code ») :
  tout est au seul nom de Julien
- ❌ Commit direct sur main (toujours PR)
- ❌ Skip CI hooks (`--no-verify`) — si ça casse, fixer le hook
- ❌ Credentials commitées — garde-fou gitleaks en pre-commit (`.pre-commit-config.yaml`,
  à activer par clone : `pre-commit install`) ; `git add` sur des chemins explicites, jamais `git add .` à l'aveugle
