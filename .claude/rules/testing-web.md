---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.mjs"
  - "**/*.vue"
  - "**/*.svelte"
---

# Testing — Web

## Outils

- Unitaires / composants : `vitest` (ou `jest` si déjà en place) + Testing Library
- E2E : `playwright` sur les parcours critiques
- Mocks réseau : `msw` plutôt que des mocks de `fetch` écrits à la main

## Règles

- Tester le comportement visible (rôles, textes), pas l'implémentation (pas de snapshot géant)
- 1 test = 1 comportement ; données de test explicites dans le test
- Pas d'appel réseau réel en CI
- Suite verte avant push

## Lancer

```bash
npm test                 # (ou pnpm / yarn / bun — celui du lockfile)
npx playwright test      # e2e
```
