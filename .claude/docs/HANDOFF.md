# HANDOFF — 2026-10-07 16h40

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `main` (conception de la spec 002 fusionnée par la PR n°4 ; la phase 0 partira sur `feature/002-phase-0`)
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (1/33 tasks : T7.1 faite)
**Goal session** : (prochaine) phase 0 : projet `banc/`, accès Vertex, `neo4j-mcp`, lanceur

## Status

- ✅ NEO-13 clos le 2026-10-07 : aucune requête humaine depuis le 2026-10-01, `reveil-aura` réussi 7 fois sur 7 ; la base est de nouveau utilisable
- ✅ PR n°3 et n°4 fusionnées en merge commit ; tag `jalon-1` sur `8d2c557` ; une branche et une PR par phase désormais (rule git-workflow)
- ✅ Spec 002 validée (option B′, revue adverse puis contre-revue), ADR-0009 ; Jira NEO-14 à NEO-24 sous NEO-2 (« En cours »), clé de chaque phase dans son titre (`tasks.md`)

## Échecs tentés (à ne pas refaire)

- Taper la séquence d'échappement de U+202F avec Write, Edit ou Bash → caractère invisible (mémoire globale `ecriture-sequences-unicode`)
- Outil Query d'Aura : `RETURN` de nœuds seuls → aucune relation dessinée ; renvoyer des chemins (ACCESS.md)

## Blocked on

- NEO-15, action de Julien : accepter les conditions de Model Garden (Sonnet 5.5, Sonnet 5, Haiku 4.5) avant T0.2

## Next (par ordre)

1. **T0.1** (NEO-14) : projet `banc/` (uv, Python 3.14, sinon 3.13), sur `feature/002-phase-0`
2. **T0.2** (NEO-15) : Model Garden par Julien, puis `banc acces` par les 3 clients ; prix, quotas et reprises relevés
3. **T0.3 et T0.4** (NEO-14) : `neo4j-mcp` v1.6.0 (somme SHA-256, variables du tag), lanceur testé sous la liste blanche
4. Phases 1 à 6, puis la phase 7 : la base étant libre, T7.2 à T7.5 peuvent avancer dès que leurs prérequis sont prêts
5. Julien : relire les 5 tables sémantiques (Q3, Q9, Q16, Q17, Q26) avant le pilote ; chronométrer la technique 1 ; mineurs : shellcheck, Prettier et pytest au pre-commit

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T0.1
Fichiers en cours: aucun
Bloqué sur: Model Garden (NEO-15, action de Julien) pour T0.2
Commande de reprise: git switch main && git pull && git switch -c feature/002-phase-0

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
