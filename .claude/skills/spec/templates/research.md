# Research — {{SPEC_TITRE}}

> Brainstorm options pour la feature `{{SPEC_ID}}-{{SPEC_KEBAB}}`.
> Rempli avec méthode par `/conception {{SPEC_ID}}-{{SPEC_KEBAB}}` (explore → options → décision → revue adverse) — ou à la main en suivant les sections.
> Append des sections datées au fil des pivots/explorations ultérieures.

**Date :** {{SPEC_DATE}}

## Problème à résoudre

{{En 2-3 phrases : qu'est-ce qu'on essaie de faire ? Pour qui ?}}

## Contraintes retenues

> Ce qui borne le plan AVANT d'explorer : cadrage client, règles de couplage (code-map.md),
> ADRs applicables (immuables), leçons déjà payées (lecons.md).

- {{Contrainte 1 : ex. doit tourner offline}}
- {{Contrainte 2 : ex. règle de couplage — X n'importe jamais Y}}
- {{Contrainte 3 : ex. ADR-0004 impose Postgres}}

## Explorations (rapports sourcés)

> Produits par les subagents parallèles de `/conception` — du factuel, jamais des impressions.

- **Code** : {{fichiers/patterns/points d'intégration — en `chemin:ligne`}}
- **Docs externes** : {{doc officielle, version exacte, pièges — URLs}}
- **Mémoire projet** : {{ADRs/leçons/idées liés — ce qui a déjà été décidé ou tenté}}

## Options considérées

### Option A — {{nom court}}

- **Comment** : {{1-2 phrases}}
- **Pros** : {{...}}
- **Cons** : {{...}}
- **Effort** : {{Petit / Moyen / Gros}}
- **Réversibilité** : {{facile à défaire ? verrouille quoi ?}}
- **Conforme couplage/ADR ?** : {{✅ | ⚠️ tension avec ... | ❌ violerait ...}}
- **Statut** : {{✅ retenu | ❌ rejeté (raison) | 🤔 à creuser}}

### Option B — {{nom court}}

- **Comment** : ...
- ...

### Option C — Ne rien faire

- **Que se passe-t-il** : {{...}}
- **Statut** : {{...}}

## Décision

{{Option retenue + raison principale + pourquoi pas les autres (1 ligne chacune).
Décision cross-feature ou qui survit à la feature → ADR (lien). Locale → § Décisions de plan.md.}}

## Revue adverse

> Findings de l'agent frais qui a challengé le plan (étape 5 de /conception) — garder la trace
> de ce qui a été attrapé évite de le re-payer.

- {{🔴/🟠/🟢 finding → correction apportée au plan}}
- {{RAS si la revue n'a rien trouvé — le noter quand même}}

## Liens externes

- {{Lien doc / blog / RFC pertinents}}
