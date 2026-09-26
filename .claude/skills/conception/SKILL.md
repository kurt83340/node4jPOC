---
name: conception
description: Planifie une feature (ou l'architecture en mode macro) AVANT de coder : exploration parallèle code/docs/mémoire par subagents, 2-3 options avec trade-offs, décision de l'utilisateur, plan.md + tasks.md vérifiables, revue adverse à contexte frais. À invoquer après /spec. Ne produit jamais de code.
allowed-tools: Read, Write, Edit, Grep, Glob, Agent, Skill, AskUserQuestion, WebFetch, WebSearch, mcp__context7, Bash(git log:*), Bash(git diff:*), Bash(grep:*), Bash(find:*)
disable-model-invocation: false
---

# /conception — Explorer, converger, arrêter le plan

> **Quand ne PAS utiliser** : pas encore de dossier spec → `/spec` d'abord · exécuter un plan
> arrêté → `/feature` (ou `/agent-teams:team`) · diagnostiquer un bug → `/debug`.
> **Réversibilité** : 🟢 n'écrit que les 4 fichiers de la spec (aucun code) —
> undo : `git checkout -- .claude/docs/conception/`.

Codifie la boucle power-user **Explore → Options → Décision → Plan → Revue adverse** sur les
artefacts EXISTANTS du template (`research.md` / `plan.md` / `tasks.md` / `spec.md`) : aucun
nouveau type de fichier — on les remplit avec méthode au lieu de les remplir à l'humeur.

**Arguments** : `/conception <spec-id>` (micro, défaut — ex. `/conception 001-livre-d-or`)
· `/conception macro` (projet entier : `conception/research.md` + `ARCHITECTURE.md` + `tasks.md`).
**Chaîne** : `/spec` (scaffold) → **`/conception`** (méthode) → exécution (solo ou `/agent-teams:team` — plugin) → `/feature-done`.
**Interdit ici** : écrire du code. Ce skill produit un PLAN, rien d'autre.

## Étape 0 — Charger les contraintes (ce qui borne le plan)

Lis AVANT d'explorer : `cadrage/README.md` (contraintes client), `conception/PRD.md` +
`ARCHITECTURE.md` (si remplis), **`code-map.md` — règles de couplage : un plan qui les viole
est mort-né**, `adr/README.md` + ADRs pertinents (décisions immuables), `lecons.md` (échecs
déjà payés), `stack.md`. → Écris « Contraintes retenues » en tête du `research.md` de la spec.

## Étape 1 — Explorer en parallèle (subagents lecture seule)

Le bruit d'exploration tue la qualité du plan → il ne rentre PAS dans ton contexte principal.
Spawne EN PARALLÈLE des **subagents** (Task tool — one-shot, invisibles ; pas des teammates) :

1. **`explore-code`** (agent) : fichiers/modules touchés, patterns à imiter, points
   d'intégration, couplages applicables → rapport en `chemin:ligne`.
2. **`explore-docs`** (agent — si lib/API/service en jeu) : doc officielle À JOUR
   (context7 → autres MCP docs → web) → API réelles, versions exactes, pièges, URLs.
3. **`explore-memoire`** (agent) : ADRs/leçons/idées/cadrage liés au sujet → ce qui a
   déjà été décidé ou tenté (et pourquoi ça a raté).

Ces trois rôles sont des **agents réutilisables** (`.claude/agents/explore-*.md`) : le rôle
et le format de rapport vivent dans leur définition (source unique) — toi tu fournis le
brief spécifique (la spec, le sujet, où chercher). Invocables aussi HORS /conception, pour
toute investigation.

Chaque rapport, factuel et sourcé → `research.md` § « Explorations » (daté ISO).

Projet **from scratch / première spec** : l'explorateur code n'a rien à lire → il explore à
la place les conventions cibles (`rules/code-style*.md`, `stack.md`) et un exemple proche si
dispo ; le poids de l'explo se déplace sur docs + cadrage.

## Étape 2 — Faire émerger 2-3 options (jamais UNE seule)

Dans `research.md` § « Options considérées », un tableau :

| Option | Approche (2 lignes) | Coût | Risques | Réversibilité | Conforme couplage/ADR ? |

Pour un choix **structurant**, génère les options par subagents indépendants à angle imposé
(MVP-first / robustesse-first / réutilisation-first) — la diversité bat l'itération.

## Étape 3 — Recommander, faire trancher

Recommandation argumentée : L'option retenue, pourquoi elle, pourquoi pas les autres →
`AskUserQuestion`. **L'utilisateur tranche, pas toi.**
Décision cross-feature ou qui survit à la feature → `/adr` ; locale → § `## Décisions` du `plan.md`.

## Étape 4 — Rédiger le plan exécutable

- `plan.md` : étapes numérotées, fichiers touchés par étape, risques + parades, et **un point
  de vérification exécutable par étape** (test/build/curl — jamais « ça devrait marcher »).
  Remplis aussi ses **§ Circuit breakers** : les conditions d'arrêt se décident À FROID, ici —
  pas au 3ᵉ échec, quand on est déjà en train de s'acharner.
- `tasks.md` : checklist `- [ ]` avec **DoD typée** (`command_passes:` / `file_exists:` /
  `manual:` — grammaire du template), **partitionnée par fichiers disjoints** si une exécution
  `/agent-teams:team` est envisagée (2 teammates sur les mêmes fichiers = interdit), et des
  phases de **~35 min de travail agent max** (au-delà : découper).
- **Mode d'exécution — décide-le ICI, par spec** (note-le dans `plan.md` § Décisions) :
  **TDD** si les comportements sont spécifiables a priori (logique métier, parsing, contrats
  d'API — le test rouge devient le point de vérification de l'étape) ; **tests-après + E2E
  ciblés** si exploratoire (UI mouvante, intégration à découvrir). `/agent-teams:team` lira ce choix.
- `spec.md` : scope / non-scope ajustés à la décision.

(Mode `macro` : mêmes étapes, sur `conception/research.md` + `ARCHITECTURE.md` + `tasks.md` —
avec deux règles v1.2 :
- **Express par défaut si le MVP tient en ≤ 3 specs** : PRD 1 page (≤ 5 features, § Scope OUT
  obligatoire), ARCHITECTURE ~10 lignes + schéma ASCII, tasks = la table de découpage seule.
  Le design profond part dans le micro de la feature 1 — on ne conçoit pas deux fois.
- **Découpage : la spec 001 = tranche verticale minimale** qui traverse le système de bout en
  bout (entrée → sortie, même moche) — dé-risque l'archi tôt et donne un démo-able en jours ;
  le transverse (erreurs, retry…) devient sa propre spec, jamais saupoudré.)

## Étape 5 — Revue adverse à contexte frais

Spawne le rôle **`reviewer`** (subagent — ou teammate visible), qui n'a PAS vu la genèse du
plan, avec pour seule mission de le **casser** :
hypothèse non vérifiée ? étape sans point de vérification ? violation code-map/ADR ? oubli
(migration, gestion d'erreur, rollback) ? tasks non partitionnées ? → findings 🔴/🟠/🟢.
Corrige le plan, et note dans `research.md` § « Revue adverse » ce qu'elle a attrapé.

## Étape 6 — Geler et brancher la suite

Validation utilisateur finale → frontmatter de `spec.md` : `status: validated` (plan arrêté —
et `in-progress` si démarrage immédiat), ROADMAP à jour (`[ ]` → `[~]` si démarrage immédiat),
HANDOFF « Next » = task 1 du plan. Propose : exécuter en solo maintenant, ou
`/agent-teams:team <spec-id>` (plugin `agent-teams` ; les tasks sont déjà partitionnées pour).

## Mode visible (tmux) — optionnel

Par défaut, explorateurs et critique sont des **subagents** (rapides, invisibles). Si
l'utilisateur veut les VOIR travailler (ou qu'une équipe tmux est déjà ouverte) : spawne-les
en **teammates** (les rôles `explore-code`, `explore-docs`, `explore-memoire`, critique =
`reviewer`) — mêmes briefs, rapport par `SendMessage`, **lead-owned** → ferme-les après débrief (rule
agent-teams). Par défaut, les deux gates (choix d'option, validation finale) se jouent dans
TA session — c'est là que vit la synthèse. Variante documentée : l'utilisateur peut répondre
**directement dans le pane** d'un teammate ; dans ce cas le teammate pose sa question en
texte, prévient le lead par `SendMessage` (« en attente décision utilisateur ») et lui
rapporte la décision. Les prompts de permission, eux, remontent TOUJOURS au lead.
Variante « pane dédié » (sans agent supplémentaire) : spawner un teammate **ad-hoc** (ex.
nommé `planner`) et taper `/conception <spec-id>` **dans son pane** — il déroule CE skill
là-bas (les teammates ont les skills du projet), l'utilisateur converse avec lui en direct,
et il rapporte le plan arrêté au lead.

## Anti-patterns

- ❌ Coder « juste un bout » pendant la conception
- ❌ Une seule option étudiée (= pas une décision, une pente)
- ❌ Option sans trade-offs / plan sans points de vérification exécutables
- ❌ Explorer dans le contexte principal (→ subagents, rapports sourcés)
- ❌ Sauter la revue adverse « parce que le plan a l'air bon » (c'est là qu'elle sert)
- ❌ Re-décider ce qu'un ADR a tranché (le superseder explicitement via `/adr` si besoin)
