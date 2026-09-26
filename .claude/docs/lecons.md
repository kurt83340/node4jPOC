# Journal des leçons

> Sas entre observation et action. Tu notes ici ce que tu observes (bugs, patterns, alertes), tu décides ensuite quoi en faire.
> **Complémentaire à auto-memory** (qui tourne automatiquement) — ici c'est la **mémoire intentionnelle versionnée**.

## Statuts

- 🆕 `new` — observé, pas décidé
- 📜 `→ ADR-00XX` — promu en ADR structurant (lien)
- 🔧 `→ rule X` — promu en règle Claude (path)
- 🧠 `→ memory only` — laissé à auto-memory (Claude apprend seul, pas besoin de plus)
- ❌ `discarded` — pas pertinent finalement
- 📦 `archived` — fermé après promotion (gardé pour historique)

## Scopes (même conv que ADR)

`cadrage` | `mvp` | `feature-00X` | `infra` | `operations`

## Workflow

```
Tu codes, tu observes
     ↓
Append une entry ici (status 🆕 new) — 4 lignes max
     ↓
Review (hebdo, fin de feature, ou via /doc-health) :
  ├─► Décision structurante  → 📜 ADR
  ├─► Convention à appliquer  → 🔧 Rule
  ├─► Pattern technique mineur → 🧠 memory only
  └─► Pas pertinent           → ❌ discarded
     ↓
Update le status
     ↓
Archive 📦 au bout de N mois (entries promues stables)
```

## Format d'une entry

```markdown
## {{YYYY-MM-DD}} — {{Titre court}}

**scope:** {{cadrage|mvp|feature-00X|infra|operations}} | **status:** {{🆕 new}}

{{Description du bug/pattern/observation en 2-4 lignes max.}}
{{Solution si déjà trouvée.}}
→ {{Décision : promouvoir en ADR / rule / discard / memory only}}
```

---

_(Aucune leçon pour l'instant — append les tiennes ici au format ci-dessus.)_
