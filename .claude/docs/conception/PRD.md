# PRD — {{PROJECT_NAME}} v1.0

> 🎯 **Pour qui** : {{stakeholders business, décideurs, validateurs produit}}
> 📋 **Ce fichier dit** : le **QUOI** + **POURQUOI** (vision, scope, personas, user stories, métriques, validations)
> ❌ **Ne contient PAS** : stack technique, modules, flux d'implémentation → voir [ARCHITECTURE.md](ARCHITECTURE.md)

**Statut :** {{Draft | Approved (décideur, date)}}
**Version :** 1.0
**Dernière MAJ :** {{YYYY-MM-DD}}
**Source :** [../cadrage/README.md](../cadrage/README.md) + {{[reunions/...](../cadrage/reunions/...)}}
**Research / brainstorm :** [research.md](research.md)

## 1. Vision

{{1-2 phrases qui résument ce qu'on construit et pour qui.}}

## 2. Problème résolu

**Aujourd'hui** : {{situation actuelle, douleurs}}

**Après** : {{situation cible, bénéfice clair}}

## 3. Personas

| Persona                          | Besoin         | Use case principal   |
| -------------------------------- | -------------- | -------------------- |
| **{{Persona 1}}** ({{nom/rôle}}) | {{besoin clé}} | {{use case typique}} |
| **{{Persona 2}}**                | ...            | ...                  |
| ...                              | ...            | ...                  |

## 4. Scope v1.0

### IN

- {{Feature/fonctionnalité 1}}
- {{Feature 2}}
- {{Contrainte technique acceptée}}
- {{Mapping de données si applicable}}

### OUT (v2+)

- {{Hors scope explicite 1}}
- {{Reporté à v2 — raison}}
- {{Non demandé}}

## 5. User stories

- **US1** En tant que {{persona}}, je veux {{action}} → CDA : {{critère d'acceptation mesurable}}
- **US2** ...
- **US3** ...

## 6. Métriques de succès

- **{{Métrique 1}}** : {{seuil mesurable}} (ex: latence p95 < X)
- **{{Métrique 2}}** : {{...}} (ex: disponibilité > Y%)
- **{{Métrique 3}}** : {{...}} (ex: adoption N utilisateurs/jour)

## 7. Hypothèses & risques

| Hypothèse       | Risque si faux  | Mitigation |
| --------------- | --------------- | ---------- |
| {{Hypothèse 1}} | {{conséquence}} | {{plan B}} |
| {{Hypothèse 2}} | ...             | ...        |

## 8. Validation

- [ ] Brief {{décideur}} : {{date}}
- [ ] PRD {{décideur}} : {{date prévue}}
- [ ] Validation tech {{owner tech}} : {{date prévue}}
- [ ] Validation finale pour mise en prod : avant {{deadline}}
