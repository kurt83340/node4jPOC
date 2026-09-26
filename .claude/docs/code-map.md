# Code Map — Intention & contraintes du code

> **Ce que Claude NE PEUT PAS deviner en lisant le code.** Pas un index : Claude
> retrouve seul le rôle d'un fichier, ses imports et ses tests via `grep`/lecture
> (agentic search). On ne documente donc QUE le non-déductible : la **vue macro**,
> les **règles de couplage**, l'**intention** et les **gotchas**.
>
> ⚠️ Avant d'éditer un fichier, vérifie les **règles de couplage** ci-dessous.

**Dernière MAJ :** {{YYYY-MM-DD}}

> 🧭 **Principe (aligné [best-practices Anthropic](https://code.claude.com/docs/en/best-practices))** :
> à EXCLURE d'ici → tout ce que Claude « peut trouver en lisant le code » : descriptions
> fichier-par-fichier, listes de dépendances, listes de tests. Ça pourrit vite (drift) et
> Claude le retrouve en un `grep`. À INCLURE → ce qui n'est pas inférable du code.
> Préférer des **pointers `chemin:ligne`** à des copies de code/structure.

## Vue d'ensemble (macro — sous-systèmes, pas fichiers)

```
{{Sous-système A}}  ──►  {{Sous-système B}}  ──►  {{Sous-système C}}
   (rôle 1 ligne)         (rôle 1 ligne)          (rôle 1 ligne)
```

→ Orientation rapide : « pour toucher X, regarde du côté de `{{dossier}}` ».
Le détail fichier-par-fichier se découvre à la demande (`grep`, lecture) — pas ici.

## Règles de couplage (⭐ le cœur — non déductible du code)

> En explorant, Claude voit ce qui **est** importé, jamais ce qui **ne doit pas** l'être.
> Ces règles négatives sont l'information la plus précieuse de ce fichier.

- ❌ `{{module_X}}` ne doit **JAMAIS** importer `{{module_Y}}` — {{raison : ex. couche métier ne connaît pas l'infra}}
- ✅ Seul `{{module_orchestrateur}}` connaît les autres modules ; les modules feuilles sont isolés
- ✅ {{Règle de sens de dépendance : ex. domaine ← application ← infrastructure, jamais l'inverse}}

## Intention & décisions locales

> Le POURQUOI qui ne se lit pas dans le code. Pour les décisions structurantes → ADR ;
> ici, les choix locaux et l'intention d'architecture.

- {{Pourquoi ce découpage : ex. on isole `{{module}}` pour pouvoir le remplacer en v2}}
- {{Pattern imposé : ex. toute requête externe passe par `{{client}}:{{ligne}}` (retry + rate-limit centralisés)}}
- {{Invariant : ex. les montants sont toujours en centimes int, jamais float}}

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
