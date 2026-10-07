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

## 2026-09-28 — Hors-périmètre fixé sans connaître l'environnement cible

**scope:** cadrage | **status:** 🧠 memory only

Le brief a exclu les briques Google Cloud avant qu'on sache que l'entreprise de Julien est full GCP avec dbt : pivot le jour même du kickoff ([CR](cadrage/reunions/2026-09-28-pivot.md)).
Solution : au kickoff, demander où le POC devra vivre ensuite (cloud, outils data, contraintes d'accès) avant de fixer le hors-périmètre.
→ Décidé le 2026-09-29 : 🧠 memory only (vue une seule fois) ; la fiche « entreprise full GCP + dbt » de la mémoire globale le rappelle à chaque kickoff.

## 2026-10-07 — Epic clos sans relire ses questions ouvertes

**scope:** operations | **status:** 🔧 → rule (skill jira, `/feature-done`)

La limite d'AuraDB Free, trouvée le 2026-09-30 par NEO-6 et notée dans `ACCESS.md`, est restée « inconnue » dans la description de l'epic NEO-1 jusqu'à sa clôture, le 2026-10-07 : la méthode ne mettait à jour que les statuts Jira, et l'epic a été clos sans être relu.
Solution : relire la description avant de passer un ticket ou un epic à « Terminé » ; ce qu'un ticket enfant trouve remonte dans le parent.
→ Décidé le 2026-10-07 : 🔧 rule, garde-fou `--relu` dans le skill jira et ligne dans `/feature-done`.
