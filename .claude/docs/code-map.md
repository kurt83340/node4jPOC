# Code Map — Intention & contraintes du code

> **Ce que Claude NE PEUT PAS deviner en lisant le code.** Pas un index : Claude
> retrouve seul le rôle d'un fichier, ses imports et ses tests via `grep`/lecture
> (agentic search). On ne documente donc QUE le non-déductible : la **vue macro**,
> les **règles de couplage**, l'**intention** et les **gotchas**.
>
> ⚠️ Avant d'éditer un fichier, vérifie les **règles de couplage** ci-dessous.

**Dernière MAJ :** 2026-10-09

## Vue d'ensemble (macro — sous-systèmes, pas fichiers)

```
Secret Manager ─┬─► scripts/ ─► cypher-shell ─► AuraDB Free ◄─ LOAD CSV ─ CSV PokéAPI (commit figé)
                │      ├─ cypher/     00 → 06 : chargement · 90 : vérification
                │      ├─ questions/  banc d'essai : requêtes et réponses de référence (jalons 1 à 4)
                │      ├─ mcp-neo4j.sh ─► neo4j-mcp (stdio, lecture seule) ─► AuraDB Free ◄─ agents de banc/
                │      └─ banc.sh ─► banc/ (clé Anthropic par l'environnement) ─► API Anthropic (Claude) · Vertex eu (Gemini)
                └─► infra/reveil-aura/ ─► Query API ─► AuraDB Free (RETURN 1 quotidien, alerte e-mail)
```

→ Orientation rapide : chargement → `cypher/NN-*.cypher` (ordre fixe : [ARCHITECTURE § 3](conception/ARCHITECTURE.md)) ;
identifiants, purge, codes retour → `scripts/` (fonctions partagées : `scripts/commun.sh`) ; banc d'essai → `questions/` ; réveil quotidien d'Aura et
son alerte → `infra/reveil-aura/` (job Cloud Run, [RUNBOOK](RUNBOOK.md)). Réponses de référence : `questions/attendu/`, rejouées par `scripts/questions.sh`.
Harnais du banc d'essai (cellules, notation, mesures) → `banc/` ([plan 002](specs/002-agent-text-to-cypher/plan.md)).
Le détail fichier-par-fichier se découvre à la demande (`grep`, lecture) — pas ici.

## Règles de couplage (⭐ le cœur — non déductible du code)

> En explorant, Claude voit ce qui **est** importé, jamais ce qui **ne doit pas** l'être.
> Ces règles négatives sont l'information la plus précieuse de ce fichier.

- ❌ Rien en dur dans `cypher/` ni `questions/` : ni identifiant, ni nom de base, ni URL de CSV. L'URL arrive par
  `$base` (`cypher-shell -P`, plan 001 D1) ; utilisateur et base valent l'identifiant de l'instance, lus dans le secret.
- ❌ Aucun chargement hors Cypher pur : ni Python, ni driver, ni CSV pré-traité hors Neo4j
  ([ADR-0003](adr/0003-mvp-chargement-cypher-pur.md)) ; tout écart passe par Julien (circuit breaker du plan 001).
- ✅ Seuls `scripts/` (poste local) et `infra/reveil-aura/` (Cloud Run) lisent les identifiants
  ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md)). `scripts/` : secret lu au lancement, les 4 `NEO4J_*`
  passés par l'environnement (`scripts/commun.sh:59`), jamais en argument ni sur le disque ; toute sortie de
  `cypher-shell` passe par `filtrer` (`scripts/commun.sh:74`). Le job : secret monté en fichier par Cloud Run,
  sous un compte qui ne lit que lui ; tout message passe par `masquer` (`infra/reveil-aura/reveil.py:161`).
  La clé Anthropic du banc ([ADR-0011](adr/0011-infra-claude-par-api-anthropic.md)) : lue par `scripts/banc.sh`,
  passée au harnais par l'environnement ; `banc/` ne lit jamais Secret Manager.
- ✅ Les agents ne joignent la base que par `scripts/mcp-neo4j.sh`, chemin absolu (plan 002, D1) : `neo4j-mcp`
  y reçoit les `NEO4J_MCP_*` (lecture seule, sans télémétrie), sans option, ni `NEO4J_*` hérité, ni accès à Claude
  (`ANTHROPIC_*`) ; stderr par `filtrer_flux` (`scripts/commun.sh:128`), stdout (canal MCP) par un masque de
  l'identifiant : `banc/` ne le voit jamais. ❌ Aucune config MCP sur le disque :
  `banc/` la passe en mémoire.
- ✅ Agents isolés par la liste blanche de `banc/src/banc/isolement.py` (plan 002, D3) : la clé Anthropic aux seules
  cellules Claude, jamais avec une variable Vertex (`CLAUDE_CODE_USE_VERTEX` passerait avant elle) ; la cellule
  Gemini ne la reçoit jamais.
- ✅ Seul le chargement (purge et preuve d'idempotence comprises) écrit dans la base : go/no-go, vérification et techniques du banc
  d'essai lisent (`--access-mode read`, `scripts/verifier.sh:45`), le réveil quotidien aussi (`accessMode: Read`,
  `infra/reveil-aura/reveil.py:119`) ; exception prévue : la mémoire d'agent (jalon 5).

## Intention & décisions locales

> Le POURQUOI qui ne se lit pas dans le code. Pour les décisions structurantes → ADR ;
> ici, les choix locaux et l'intention d'architecture.

- Vérification d'abord (plan 001, D8) : `scripts/verifier.sh` s'écrit avant les chargements ; rouge sur base
  vide (code 1), chaque fichier `cypher/` le fait passer au vert section par section (`--section`).
- Idempotence : `cypher/00-contraintes.cypher` passe avant tout `MERGE` ; chaque `MERGE` porte sur une clé
  contrainte (identifiant PokéAPI, plan 001, D2) ou sur un chemin (`Description`) ; une relance ne crée rien (T6.1).
- Codes retour communs à tous les scripts : 0 succès · 1 écart constaté · 2 erreur technique (`scripts/commun.sh:8`).
- Reproductibilité : tout part du commit PokéAPI figé (`scripts/commun.sh:22`, [ADR-0001](adr/0001-mvp-jeu-de-donnees-pokeapi.md)) ;
  changer de commit change les réponses de référence de `questions/`.

## Gotchas → `code-map-gotchas.md`

Pièges dans [code-map-gotchas.md](code-map-gotchas.md) (non auto-chargé : le hook injecte ceux du fichier édité).
Ce fichier-ci est auto-chargé à chaque session : **< 3k tokens**.

## Quand mettre à jour ce fichier

- Règle de couplage ou contrainte d'architecture nouvelle → l'ajouter ; découpage modifié → revoir la vue macro.
- Piège lié à un fichier → `code-map-gotchas.md` ; ❌ jamais de description fichier par fichier ni de dépendances.
- Entretien : `/codemap` (vue macro, violations de couplage par grep).
