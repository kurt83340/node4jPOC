# Code Map — Intention & contraintes du code

> **Ce que Claude NE PEUT PAS deviner en lisant le code.** Pas un index : Claude
> retrouve seul le rôle d'un fichier, ses imports et ses tests via `grep`/lecture
> (agentic search). On ne documente donc QUE le non-déductible : la **vue macro**,
> les **règles de couplage**, l'**intention** et les **gotchas**.
>
> ⚠️ Avant d'éditer un fichier, vérifie les **règles de couplage** ci-dessous.

**Dernière MAJ :** 2026-09-30

> 🧭 **Principe (aligné [best-practices Anthropic](https://code.claude.com/docs/en/best-practices))** :
> à EXCLURE d'ici → tout ce que Claude « peut trouver en lisant le code » : descriptions
> fichier-par-fichier, listes de dépendances, listes de tests. Ça pourrit vite (drift) et
> Claude le retrouve en un `grep`. À INCLURE → ce qui n'est pas inférable du code.
> Préférer des **pointers `chemin:ligne`** à des copies de code/structure.

## Vue d'ensemble (macro — sous-systèmes, pas fichiers)

```
Secret Manager ─┬─► scripts/ ─► cypher-shell ─► AuraDB Free ◄─ LOAD CSV ─ CSV PokéAPI (commit figé)
                │      ├─ cypher/     00 → 06 : chargement · 90 : vérification
                │      └─ questions/  banc d'essai : requêtes et réponses de référence (jalons 1 à 4)
                └─► infra/reveil-aura/ ─► Query API ─► AuraDB Free (RETURN 1 quotidien, alerte e-mail)
```

→ Orientation rapide : chargement → `cypher/NN-*.cypher` (ordre fixe : [ARCHITECTURE § 3](conception/ARCHITECTURE.md)) ;
identifiants, purge, codes retour → `scripts/` (fonctions partagées : `scripts/commun.sh`) ; banc d'essai → `questions/` ; réveil quotidien d'Aura et
son alerte → `infra/reveil-aura/` (job Cloud Run, [RUNBOOK](RUNBOOK.md)). `cypher/02` à `06` et `questions/qNN.cypher` : à venir (T4.3 à T7.1).
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
  passés par l'environnement (`scripts/commun.sh:53`), jamais en argument ni sur le disque ; toute sortie de
  `cypher-shell` passe par `filtrer` (`scripts/commun.sh:68`). Le job : secret monté en fichier par Cloud Run,
  sous un compte qui ne lit que lui ; tout message passe par `masquer` (`infra/reveil-aura/reveil.py:161`).
- ✅ Seul le chargement (purge comprise) écrit dans la base : go/no-go, vérification et techniques du banc
  d'essai lisent (`--access-mode read`, `scripts/verifier.sh:45`), le réveil quotidien aussi (`accessMode: Read`,
  `infra/reveil-aura/reveil.py:119`) ; exception prévue : la mémoire d'agent (jalon 5).

## Intention & décisions locales

> Le POURQUOI qui ne se lit pas dans le code. Pour les décisions structurantes → ADR ;
> ici, les choix locaux et l'intention d'architecture.

- Vérification d'abord (plan 001, D8) : `scripts/verifier.sh` s'écrit avant les chargements ; rouge sur base
  vide (code 1), chaque fichier `cypher/` le fait passer au vert section par section (`--section`).
- Idempotence : `cypher/00-contraintes.cypher` passe avant tout `MERGE` ; chaque `MERGE` porte sur une clé
  contrainte (identifiant PokéAPI, D2) ou sur un chemin (`Description`) ; une relance ne crée rien (T6.1).
- Codes retour communs à tous les scripts : 0 succès · 1 écart constaté · 2 erreur technique (`scripts/commun.sh:8`).
- Reproductibilité : tout part du commit PokéAPI figé (`scripts/charger.sh:16`, [ADR-0001](adr/0001-mvp-jeu-de-donnees-pokeapi.md)) ;
  changer de commit change les réponses de référence de `questions/`.

## Gotchas → `code-map-gotchas.md`

Les pièges non évidents vivent dans [code-map-gotchas.md](code-map-gotchas.md) (**non auto-chargé**) :
le hook PreToolUse n'injecte que ceux qui citent le fichier en cours d'édition. Ici ne restent que
la vue macro, le couplage et l'intention — ce fichier est auto-chargé à chaque session : **< 3k tokens**.

## Quand mettre à jour ce fichier

- Nouvelle **règle de couplage** ou contrainte d'architecture → l'ajouter
- Découpage en sous-systèmes modifié → revoir la vue macro
- Nouveau **gotcha** découvert (un piège qui t'a coûté du temps) → le noter
- ❌ **NE PAS** ajouter de description fichier-par-fichier ni de liste de dépendances : Claude les retrouve seul, et elles drifteraient.

> 🔁 **Entretien** : le skill `/codemap` régénère la vue macro et **détecte les violations
> de couplage** (par grep des imports). Ce fichier est déjà en contexte (`@`) : le hook
> `pretooluse-inject-codemap.py` n'injecte que les **gotchas qui ciblent le fichier édité**
> (1×/fichier/session) — pas une carte structurelle (déductible et périssable).
