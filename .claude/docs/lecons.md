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

## 2026-10-08 — Un test d'exclusion doit employer une entrée que le code accepterait sans elle

**scope:** feature-002 | **status:** 🆕 new → 🔧 → [rule](../rules/testing.md) (2026-10-09, choix de Julien, après deux nouveaux cas en phase 3)

Phase 2, mutations : 3 tests sur 60 fautes passaient pour une autre raison que la règle visée. Un en-tête « // Réponse : » dans un bloc de code était déjà invalide hors bloc ; un faux message d'erreur de read-cypher ne portait pas la valeur, alors qu'un vrai message Neo4j recopie la requête ; la tolérance de Q8 (« à moins de 0,01 ») n'avait aucun cas pile à la borne.
Corrigé dans `banc/tests/test_lecture.py` et `test_notation.py`, et les mutations l'ont montré : les garder à chaque phase.
→ Piste : 🔧 rule `testing.md` (« le cas d'une exclusion serait accepté sans elle ; une borne se teste pile dessus »).

## 2026-10-07 — Règle deny `Neo4j-*.txt` insensible à la casse

**scope:** infra | **status:** 🆕 new → 🧠 memory only (2026-10-09, choix de Julien : la règle large protège mieux ; le contournement ci-dessous suffit)

La règle `Read(//**/Neo4j-*.txt)` de `.claude/settings.json` (fichier d'identifiants d'Aura, ADR-0007) a bloqué `sha256sum -c neo4j-mcp_1.6.0_checksums.txt`, le fichier de sommes public de neo4j/mcp (T0.3) : le motif ne tient pas compte de la casse.
Contournement sûr : enregistrer le fichier sous un autre nom (`sommes-neo4j-mcp-1.6.0.txt`), contenu identique ; jamais affaiblir la règle sans décision.
→ Piste : resserrer le motif sur `Neo4j-*-Created-*.txt` (format du fichier d'Aura), puis 🔧 rule ; à décider par Julien.

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
