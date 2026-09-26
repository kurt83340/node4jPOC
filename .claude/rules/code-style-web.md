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

# Code style — Web (TypeScript / JavaScript)

## Outils

- TypeScript `strict` pour le code neuf (pas de `any` implicite — `unknown` + garde de type)
- Formatter / linter : ceux du projet (`prettier` + `eslint`, ou `biome`), lancés avant commit
- Gestionnaire de paquets : celui du lockfile présent (npm / pnpm / yarn / bun) — jamais deux

## Conventions

- Modules ES, imports explicites (pas de barrel `index.ts` géant qui crée des cycles)
- 1 composant par fichier, nommé comme le fichier (`UserCard.tsx`)
- État local d'abord ; global seulement s'il est réellement partagé
- Accessibilité : éléments natifs (`button`, `a`, `label`), textes alternatifs, focus visible

## Naming

- `camelCase` variables/fonctions · `PascalCase` composants/types/classes · `UPPER_SNAKE` constantes
- Fichiers : `kebab-case.ts` pour les modules, `PascalCase.tsx` pour les composants

## Erreurs

- Jamais de `catch {}` vide — logger ou remonter avec contexte
- Erreurs d'API typées côté client (résultat `{ ok, error }` ou erreurs dédiées), jamais de chaîne nue
- Aucun secret côté client (seules les variables publiques du framework, ex. `NEXT_PUBLIC_*`)
