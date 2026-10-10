---
status: accepted
scope: infra
phase: 2026-Q4
supersedes: null
amends: 0010
---

# 0013 — Plafond natif mensuel de Vertex, en plus de la coupure de l'option C

**Statut :** Accepted
**Date :** 2026-10-10
**Décideur :** Julien Leroy

## Contexte

L'[ADR-0010](0010-infra-plafond-de-depense.md) a retenu l'option C : à 100 € dépensés sur `jleroy-labo` depuis le 2026-10-01, une fonction désactive `aiplatform.googleapis.com`. Avant de la construire (NEO-26), la doc de Google, relue le 2026-10-10, change quatre choses :

- **Retard** : un budget voit les coûts « typically within a day, but can sometimes take more than 24 hours » ([budgets et plafonds](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps), mise à jour le 2026-10-07). L'ADR-0010 parlait de « quelques heures ». La coupure de l'option C peut donc arriver plus d'un jour après le dépassement.
- **Plafond natif** : les « spend cap budgets », en Preview depuis le 2026-07-27, couvrent « Gemini Enterprise Agent Platform (formerly Vertex AI) », appels d'ADK compris. Ils suspendent tout nouvel usage en quelques minutes, sur des coûts estimés. L'option E de l'ADR-0010 avait été écartée parce que rien ne disait que Claude, facturé par la Marketplace, était couvert. Depuis l'[ADR-0011](0011-infra-claude-par-api-anthropic.md), Claude ne passe plus par Vertex : seul Gemini y reste, et il est couvert.
- **Droits** : aucun rôle prédéfini ne se limite à désactiver un service. `roles/serviceusage.serviceUsageAdmin` permet aussi d'en activer. D'où un rôle personnalisé, qui ne contient que `serviceusage.services.get` et `serviceusage.services.disable` : les deux sont permises dans un rôle personnalisé (`gcloud iam list-testable-permissions`, 2026-10-10).
- **Fin du budget** : « Budgets with an elapsed end date are expired and don't recur » ([budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets)). Après le 2026-12-31, le budget de 100 € n'envoie plus rien, et la coupure ne se déclenche plus, sans prévenir.

## Options considérées

- **Option A — option C seule**, telle que décidée : tient le cumul de 100 € sur trois mois et garde Vertex coupé jusqu'à un geste volontaire, mais réagit avec le retard du budget.
- **Option B — option C et plafond natif mensuel** : le plafond natif arrête vite une dépense qui s'emballe, et la fonction tient le cumul.
- **Option C — plafond natif seul** : ni code ni fonction ; mais mensuel, levé tout seul le 1er du mois, en Preview sans garantie de service, et sans cumul sur trois mois.
- **Option D — ne rien changer à l'ADR-0010** : laisser le retard réel et l'expiration du budget hors de la décision.

## Décision

**Option B** (Julien, 2026-10-10). Le point remplacé dans l'ADR-0010 est la décision « Option C » : la coupure de l'option C est complétée par un plafond natif de **30 € par mois** sur Vertex, budget « Plafond natif Vertex jleroy-labo (mensuel) » (service de facturation `C7E2-9256-1C43`).

- **Fonction** ([`infra/coupure-vertex/`](../../../infra/coupure-vertex/), NEO-26) : elle coupe dès que le coût cumulé **atteint** le budget (`>=`), alors que l'exemple de Google n'agit qu'au-delà. Elle relit l'état de Vertex avant d'agir, car les messages arrivent plusieurs fois par jour, parfois en double. Elle ne réactive jamais rien, et elle s'exécute sous le rôle personnalisé `coupureVertex`.
- **Plafond natif** : trois mois à 30 € font 90 €, sous les 100 € ; c'est large pour Gemini Flash sur le banc. Il est créé une fois par l'API Budget, puisque gcloud n'a pas de commande pour lui.

## Conséquences

- ✅ Une dépense qui s'emballe sur Vertex s'arrête en quelques minutes, et non plus après un jour ou davantage. Le plafond de campagne du banc couvre déjà ses propres appels en direct (plan 002, D13).
- ✅ Les deux garde-fous restent gratuits : le plafond natif n'a pas de frais, et la fonction tient dans les paliers gratuits de Cloud Run, Pub/Sub, Eventarc, Cloud Build et Artifact Registry.
- ⚠️ Le plafond natif compte des coûts bruts estimés, sans crédits. Il se lève tout seul le 1er de chaque mois, et Google refuse de le modifier tant qu'il agit. La doc ne précise pas l'erreur que reçoit un client : à relever en T5.1.
- ⚠️ Preview : pas de garantie de service. L'option C reste le garde-fou de référence.
- ⚠️ Le budget de 100 € expire le 2026-12-31 : le prolonger ou le remplacer avant cette date. Le plafond natif, mensuel, continue après.

## Liens

- [ADR-0010](0010-infra-plafond-de-depense.md) : la décision amendée, en vigueur pour le reste
- [ADR-0011](0011-infra-claude-par-api-anthropic.md) : Claude par l'API Anthropic, hors de Vertex
- [RUNBOOK](../RUNBOOK.md), section « Coupure de Vertex » : essais, réactivation, levée du plafond natif
- Doc Google, lue le 2026-10-10 : [plafonds natifs](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps), [API Budget et plafond](https://docs.cloud.google.com/billing/docs/how-to/budget-api-spend-cap), [notifications programmatiques](https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications), [désactiver un service](https://docs.cloud.google.com/service-usage/docs/reference/rest/v1/services/disable)
