# Research — Conception macro projet

> Brainstorm initial + exploration d'options + capture des pivots ultérieurs.
> Au niveau **projet entier** (pas au niveau d'une feature — celui-là vit dans `specs/00X-feature/research.md`).

## {{YYYY-MM-DD}} — Brainstorm initial

### Question de départ

{{Reformule la question business en question technique : "Comment faire X en respectant Y et Z contraintes ?"}}

### Options explorées

#### Option 1 — {{Approche A}}

- **Pour** : {{avantages}}
- **Contre** : {{inconvénients, dette technique}}
- **Effort** : {{X semaines}}
- **Décision** : {{✅ retenu | ❌ rejeté (raison)}}

#### Option 2 — {{Approche B}}

- **Pour** : ...
- **Contre** : ...
- **Décision** : ...

#### Option 3 — {{Approche C}}

- ...

### Questions ouvertes initiales (à clarifier au kickoff)

- {{Question 1}} → {{réponse | à clarifier avec X}}
- {{Question 2}} → ...

### Hypothèses retenues pour le PRD

- {{Hypothèse 1}}
- {{Hypothèse 2}}
- {{Hypothèse 3}}

### Décisions issues du brainstorm

1. {{Décision 1}} → ADR-00XX
2. {{Décision 2}} → ADR-00XX
3. {{Décision 3}} → pas d'ADR (mineur)

---

## Template pour pivots ultérieurs

Si la hiérarchie demande un pivot, append ici une section datée :

```markdown
## YYYY-MM-DD — Pivot [titre]

### Contexte du pivot

Pourquoi on doit changer (réunion, mail, ticket → voir cadrage/reunions/)

### Nouvelles options explorées

- Option A : ...
- Option B : ...

### Décision retenue

- ...

### Conséquences

- PRD bumpé v1.0 → v2.0
- ROADMAP refondu (voir ../ROADMAP.md section v2)
- ADR-00XX créé si pivot tech
```
