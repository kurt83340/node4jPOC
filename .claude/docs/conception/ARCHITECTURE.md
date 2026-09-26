# Architecture — {{PROJECT_NAME}} v1.0

> 🛠️ **Pour qui** : {{owner tech / devs / futurs devs qui reprennent le code}}
> 📋 **Ce fichier dit** : le **COMMENT technique** (composants, stack, modules, flux de données, sécurité, observabilité)
> ❌ **Ne contient PAS** : vision business, user stories, métriques produit → voir [PRD.md](PRD.md)

**Statut :** {{Draft | Validée par {{owner tech}} {{date}}}}
**Dernière MAJ :** {{YYYY-MM-DD}}

## 1. Vue d'ensemble

### Composants techniques

```
{{ASCII art : qui parle à qui — sources, destinations, services tiers}}

┌─────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│  {{Source}}     │ ─────►  │  {{Orchestrator}}│ ─────►  │  {{Destination}} │
└─────────────────┘         └──────────────────┘         └──────────────────┘
```

### Séquence d'un run (si applicable)

```
[Trigger]
     │
     ├─► Étape 1 : ...
     ├─► Étape 2 : ...
     │       │
     │       ├─ Cas A : ...
     │       └─ Cas B : ...
     │
     └─► Étape finale
```

### Légende / états (si applicable)

| État      | Description |
| --------- | ----------- |
| `STATE_A` | ...         |
| `STATE_B` | ...         |

→ Pour la **vision business** (flow client) : [../cadrage/diagrams/{{flow-X}}.md](../cadrage/diagrams/) (si créé)

## 2. Stack technique (vue archi)

Stack résumé des choix **structurants** avec ADR liés.
→ **Inventaire complet** (libs + services tiers + LLM + deploy) : [../stack.md](../stack.md)

| Couche            | Choix          | Justification | ADR                               |
| ----------------- | -------------- | ------------- | --------------------------------- |
| {{Orchestration}} | **{{techno}}** | {{raison}}    | [{{XXXX}}](../adr/{{XXXX}}-...md) |
| {{Backend}}       | **{{techno}}** | ...           | -                                 |
| {{Stockage}}      | **{{techno}}** | ...           | -                                 |
| {{Auth}}          | ...            | ...           | -                                 |
| {{Logging}}       | ...            | ...           | -                                 |

## 3. Modules & découpage

Décris ici le **découpage macro en sous-systèmes** (qui fait quoi, à gros grain) — voir aussi la vue d'ensemble §1. **Pas** de détail fichier-par-fichier (rôle, méthodes, liste de tests) : ça se retrouve en lisant le code (`grep`/lecture) et ça drifte.

> ⚠️ Ce qui **n'est PAS déductible du code** — règles de couplage, intention, gotchas — vit dans **[../code-map.md](../code-map.md)** (auto-chargé ; ses gotchas, dans `code-map-gotchas.md`, sont injectés par hook à l'édition du fichier ciblé). Ne pas le dupliquer ici.

## 4. Flux de données

1. **{{Étape 1}}** : {{description technique}}
2. **{{Étape 2}}** : {{...}}
3. **{{Étape N}}** : {{...}}

## 5. Mapping champs (si applicable)

| Source             | Destination      | Transformation |
| ------------------ | ---------------- | -------------- |
| `{{champ_source}}` | `{{champ_dest}}` | {{conversion}} |
| ...                | ...              | ...            |

## 6. Sécurité

- Credentials : {{où stockés, comment}}
- {{Permissions / scopes}}
- {{Communication / VPN / TLS}}
- Logs : {{anonymisation des données sensibles}}

## 7. Observabilité

- **{{Monitoring 1}}** : {{rétention, ce qui est surveillé}}
- **{{Sentry / autre}}** : {{alerting critique}}
- **{{Alerts}}** : {{seuils, destinataires}}

## 8. Évolutions prévues (v2+)

- {{Évolution 1 — quand / si X}}
- {{Évolution 2}}
- {{Évolution 3}}
