# HANDOFF — 2026-10-13 00h50

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/003-conception`, PR n°21 de conception vers `main` (NEO-3), CI lancée
**Spec en cours** : [003-graphrag-descriptions](specs/003-graphrag-descriptions/spec.md) (0/35 tasks, validée le 2026-10-13)
**Goal session** : poser le jalon 3 avec toute la méthode : spec, conception, revue adverse, tickets

## Status

- ✅ Jalon 2 clos : PR n°20 fusionnée, tag `jalon-2` sur `a8dd937`, NEO-2 et ses tickets « Terminé »
- ✅ Conception 003 validée par Julien : option A′ (plugin GenAI au chargement, question encodée par le banc, recherche par `read-cypher`), cellules Claude Sonnet 5.5 et Gemini 3.8 Flash, recherche vectorielle seule, index de 3 072 dimensions ; 18 phases, 35 tâches ; coût estimé 8 $ (plafond de la spec 10 $)
- ✅ Instance, gratuit : « 5.27-aura », plugin GenAI présent, `SEARCH`, `params` de `read-cypher`, `:param` évalué côté serveur ; test payant (~0,00001 $) : lot de 2 textes, `task_type` en snake_case, plugin = google-genai, `eu` refusé (`europe-west1`)
- ✅ ADR-0018 (technique sans outil), 0019 (jeton Vertex du plugin), 0020 (index des descriptions) ; ACCESS : compte `aura-genai` (créé le 2026-10-12, `roles/aiplatform.user` jusqu'à T3.2)
- ✅ Revue adverse (1 🔴, 9 🟠, 14 🟢) et contre-vérification (8 🟠) reprises ; Jira : NEO-28 à NEO-35 sous NEO-3 (« En cours »), NEO-28 et NEO-29 « À faire » ; scripts de la session dans `logs/outils/jalon-3/`

## Échecs tentés (à ne pas refaire)

- Script de mutation sans `finally` → arrêté en route, il a laissé le fichier muté : copie d'abord, motif unique vérifié, restauration dans un `finally`
- Jeton du chargement décidé « au lancement » (première correction du plan) → une purge recrée des descriptions sans vecteur : décider juste avant `07`

## Blocked on

- L'accord de Julien pour fusionner la PR n°21 (CI verte d'abord)

## Next (par ordre)

1. **Fusion** de la PR n°21 (merge commit, `gh pr checks 21` vert), sur l'accord de Julien
2. **Phase 1, T1.1** (NEO-28 « En cours ») : `banc contre-epreuve` en TDD depuis `logs/outils/`, branche `feature/003-phase-1`
3. **T2.2** (NEO-29, action de Julien) : nouvelle clé Anthropic avant le pilote (l'actuelle expire le 2026-11-07)

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 003-graphrag-descriptions
Task: T1.1
Fichiers en cours: aucun
Bloqué sur: accord de Julien pour fusionner la PR n°21
Commande de reprise: gh pr checks 21

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
