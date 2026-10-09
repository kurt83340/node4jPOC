# HANDOFF — 2026-10-09 18h50

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/002-phase-4` (T4.1 et T4.2 poussées ; PR de la phase après T4.3)
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (14/33 tasks : phases 0 à 3, T4.1, T4.2, T7.1)
**Goal session** : T4.2, les cellules ADK (Claude par l'API, Gemini par Vertex), vérifiées sur le vrai ADK

## Status

- ✅ `banc/` : 916 tests, ruff, mypy strict, shellcheck, gitleaks propres ; couverture de `banc.cellule_adk` 99 % ; aucun appel LLM (0 $)
- ✅ T4.2 : `banc.cellule_adk`, vrai ADK 2.11.0 contre une fausse API Anthropic et Vertex et un faux serveur MCP ; revue adverse en deux passes (13 constats) traitée ; 96 fautes injectées, 95 détectées, 1 équivalente ; NEO-18 « En cours »
- ✅ Choix de Julien : `max_tokens` 128 000 (flux), 2 reprises pour Gemini, appel coupé compté 0, `GOOGLE_*` ôtées par le lanceur, garde-fou de budget sur un résultat énorme

## Échecs tentés (à ne pas refaire)

- Crochets httpx sur google-genai → sans effet, il passe par aiohttp : reprises lues dans son journal ([gotcha](code-map-gotchas.md))
- Usage lu sur les événements d'ADK → une réponse vide de Gemini s'y perd : `after_model_callback`
- Remonter la chaîne d'une erreur de flux → vide (`httpx2.ResponseNotRead` d'ADK) : panne d'office

## Blocked on

- Rien

## Next (par ordre)

1. **T4.3 (NEO-18)** : orchestration (groupe de processus, SIGTERM avant SIGKILL : la cellule ADK arrête son serveur, qui vit dans sa propre session, puis sort en 143 ; `scripts/transactions.sh`, relances, ligne de Q18 après l'échec de Q2 selon l'ADR-0012, alternance, `--reprendre`), puis PR de la phase 4 `(NEO-18)`
2. Avant toute campagne payante (au plus tard T5.1) : coupure automatique de l'ADR-0010, branche à part
3. En T5.1, relever : `tool_use_prompt_token_count` de Gemini (s'il vient, la mesure s'arrête) ; morceau partiel d'un appel Gemini coupé (cache compté plein sans `cachedContentTokenCount`)
4. À trancher et mineurs : un ADR qui précise l'ADR-0009 (plafonds invisibles, instructions ôtées, garde-fou, reprises et sortie alignées) ? ; leçon du 2026-10-09 en rule (méthode servie deux fois) ; pre-commit (shellcheck, Prettier, pytest) ; flag des équipes en portée user

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T4.3
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch feature/002-phase-4 && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
