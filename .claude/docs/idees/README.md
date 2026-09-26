# idees/ — Brouillons d'idées perso

> Tes idées brutes (input INTERNE). À ne pas confondre avec `../cadrage/` (input EXTERNE = client).

## Convention de naming

`YYYY-MM-DD-titre-court.md`

Exemples :

- `2026-05-22-sync-inverse.md`
- `2026-05-23-slack-alerts.md`
- `2026-06-01-cache-redis.md`

## Format d'une idée (libre, court)

```markdown
# Idée — {{Titre}}

**Date :** YYYY-MM-DD
**Source :** {{discussion avec X, en codant, après tel article, etc.}}

## Pitch

{{1-2 phrases. Quelle valeur pour qui ?}}

## Use case

{{Scénario concret}}

## Effort estimé

{{Petit (< 1 jour) | Moyen (~1 sem) | Gros (> 1 sem)}}

## Statut

💡 **{{Backlog | À promouvoir en spec | Discuter avec X | Abandonné}}**
```

## Workflow

```
1. Idée vague → 1 fichier daté ici
       ↓
2. Idée mûrit → décider :
   ├─► Promouvoir en feature → créer `../specs/00X-feature/`
   ├─► Modifier la roadmap → update `../ROADMAP.md` backlog
   └─► Abandonner → supprimer ou marquer "❌ abandonné"
```

## Différence avec ailleurs

| Fichier                  | Source           | Maturité                     |
| ------------------------ | ---------------- | ---------------------------- |
| `cadrage/`               | Client (externe) | Capture brute                |
| **`idees/` ICI**         | Toi (interne)    | Idée pas mûre                |
| `conception/research.md` | Toi (interne)    | Brainstorm structuré projet  |
| `specs/00X/research.md`  | Toi (interne)    | Brainstorm structuré feature |
