# Stack — {{PROJECT_NAME}}

> **Catalogue technique pur** : langage, libs, services tiers, LLM, infra/deploy.
> Le **POURQUOI** des choix vit dans [adr/](adr/). L'**ARCHI** globale (dont **sécurité** & **observabilité**) dans [conception/ARCHITECTURE.md](conception/ARCHITECTURE.md) ; les **conventions de test** dans [../rules/testing.md](../rules/testing.md).
> Ce fichier = **vue catalogue rapide** ("quelles techs on utilise et pour quoi ?") — **pas** de narratif archi/sécurité/tests ici (sinon drift avec ARCHITECTURE).

**Dernière MAJ :** {{YYYY-MM-DD}}

## Langage(s) & runtime

| Item                   | Version   | Notes           |
| ---------------------- | --------- | --------------- |
| {{Python / Node / Go}} | {{X.Y.Z}} | {{env manager}} |
| {{Autre runtime}}      | ...       | ...             |

## Orchestration

| Composant           | Choix          | Voir                     |
| ------------------- | -------------- | ------------------------ |
| {{Workflow engine}} | **{{techno}}** | [{{ADR-XXXX}}]({{path}}) |
| {{Scheduling}}      | ...            | —                        |

## Stockage & data

| Source/Destination | Usage                          | Voir                |
| ------------------ | ------------------------------ | ------------------- |
| **{{System 1}}**   | {{lecture / écriture / cache}} | [{{ADR}}]({{path}}) |
| **{{System 2}}**   | ...                            | ...                 |

## Librairies (rôles)

| Lib         | Version | Pour quoi | Module qui l'utilise |
| ----------- | ------- | --------- | -------------------- |
| `{{lib_1}}` | ^{{X}}  | {{usage}} | {{module}}           |
| `{{lib_2}}` | ^{{X}}  | ...       | ...                  |
| ...         | ...     | ...       | ...                  |

## LLM providers (par feature)

| Feature                            | LLM utilisé | Coût estimé | Notes              |
| ---------------------------------- | ----------- | ----------- | ------------------ |
| _(aucun usage LLM pour l'instant)_ | —           | —           | {{type de projet}} |

⚠️ **Si une feature utilise un LLM**, documenter ici **ET** dans `specs/00X-feature/plan.md` (section "LLM choisi + raison + coût estimé").

Options à considérer si besoin :

- Claude Sonnet 4.6 / 4.7 (raisonnement)
- Claude Haiku 4.5 (rapide, peu coûteux)
- GPT-4o / GPT-5 (si client préfère OpenAI)

## Services tiers / SaaS

| Service                   | Usage                | Statut                       | Coût               | Voir                              |
| ------------------------- | -------------------- | ---------------------------- | ------------------ | --------------------------------- |
| **{{Sentry / autre}}**    | {{error tracking}}   | {{✅ actif / ⏳ en attente}} | {{free / X€/mois}} | [{{lien}}]({{path}})              |
| **{{Vault credentials}}** | {{stockage secrets}} | {{actif}}                    | {{inclus}}         | `ACCESS.md` _(créé à la demande)_ |
| ...                       | ...                  | ...                          | ...                | ...                               |

❌ **Pas utilisé** : {{liste des services explicitement écartés}}.

## Infra & Deploy

| Item        | Choix                                 | Notes                                            |
| ----------- | ------------------------------------- | ------------------------------------------------ |
| Hébergement | {{cloud / on-prem / spécifique}}      | {{contrainte}}                                   |
| CI/CD       | {{GitHub Actions / GitLab CI / etc.}} | {{lint + tests sur PR}}                          |
| Versioning  | Tags git `vYYYY.MM.DD-HHMM`           | Voir [git-workflow.md](../rules/git-workflow.md) |

## Hors de ce catalogue (home unique — ne pas dupliquer ici)

Pour éviter le drift, ces aspects vivent **ailleurs** (ce fichier ne fait que pointer) :

- **Auth & sécurité** (patterns auth, secrets storage, anti-patterns credentials) → [conception/ARCHITECTURE.md](conception/ARCHITECTURE.md) §6 Sécurité
- **Monitoring & observabilité** (logs, metrics, alerting, rétention) → [conception/ARCHITECTURE.md](conception/ARCHITECTURE.md) §7 Observabilité
- **Tests** (frameworks, couverture, commandes) → [../rules/testing.md](../rules/testing.md)

## Évolutions stack prévues (v2+)

- {{Si volume X → ajouter Y}}
- {{Migration prévue}}
- {{Refacto attendu}}

## Mise à jour

- **Nouvelle lib ajoutée** : update la table "Librairies"
- **Nouveau service SaaS** : update "Services tiers"
- **Feature ajoute usage LLM** : update "LLM providers" + référencer dans specs/00X/plan.md
- **Changement infra** : update "Infra & Deploy"
- **Source of truth** : `{{pyproject.toml | package.json}}` pour les libs exactes (versions), CE fichier pour le contexte humain (WHY + services tiers + LLM)
