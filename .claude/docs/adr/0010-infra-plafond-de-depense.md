---
status: accepted
scope: infra
phase: 2026-Q4
supersedes: null
---

# 0010 — Plafond de dépense : budget de 100 € et coupure automatique de Vertex

**Statut :** Accepted
**Date :** 2026-10-07
**Décideur :** Julien Leroy

## Contexte

La spec 002 fait les premiers appels payants du POC : des LLM sur Vertex (Claude et Gemini), estimés à 22 à 31 € pour toute la spec, et les jalons 3 et 4 en feront d'autres. Le 2026-10-07, avant ces appels (T0.2), Julien fixe la règle : « je dois avoir une vue sur les dépenses et rien qui dépasse 100 euros pour l'instant ». Un seul budget existait, « Budget mensuel GCP » (10 €/mois sur tout le compte de facturation), qui ne fait qu'envoyer des e-mails. Un budget Google Cloud n'arrête rien de lui-même, et les coûts lui parviennent avec quelques heures de retard ([doc des budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets), mise à jour le 2026-10-05).

## Options considérées

- **Option A — alertes seules** : un budget de 100 € et ses e-mails ; rien ne s'arrête si personne ne lit.
- **Option B — alertes et plafond du banc** : le harnais refuse de lancer une conversation au-delà d'un montant cumulé, calculé en direct sur les tokens ; ne couvre que les dépenses du banc.
- **Option C — alertes et coupure automatique de l'API Vertex** : à 100 €, une fonction désactive `aiplatform.googleapis.com` sur `jleroy-labo` ; Claude et Gemini s'arrêtent, le reste du projet continue (`reveil-aura`, secrets).
- **Option D — coupure de toute la facturation du projet** (modèle documenté par Google) : arrête aussi `reveil-aura` et Secret Manager, donc le socle du jalon 1.
- **Option E — plafonds natifs de Google (« spend cap budgets »)** : un seul service par budget, période mensuelle ; Agent Platform est couvert, mais rien ne dit que Claude, facturé via Marketplace, l'est.
- **Option F — ne rien faire** : le budget global de 10 €/mois, qui alerte sans arrêter.

## Décision

**Option C** (Julien, 2026-10-07), avec les garde-fous du banc.

- **Fait le 2026-10-07** : budget « Plafond jleroy-labo 100 EUR (oct-dec 2026) », 100 € cumulés du 2026-10-01 au 2026-12-31, filtré sur `jleroy-labo`, alertes par e-mail à 25, 50, 75, 90 et 100 % ; le budget global de 10 €/mois reste en place comme alerte précoce. Les deux s'affichent dans `/google-facture`.
- **À construire avant toute campagne** : le budget publie dans un sujet Pub/Sub ; une fonction Cloud Run, sous un compte de service qui ne peut que désactiver un service de `jleroy-labo`, désactive `aiplatform.googleapis.com` dès que le coût atteint le budget. Remise en service à la main, décrite dans le RUNBOOK.
- **Garde-fous du banc, immédiats** : coût calculé en direct à partir des tokens et de `banc/prix.toml` ; budget par conversation ; arrêt si le pilote dépasse 1,5 fois l'estimation ([plan 002](../specs/002-agent-text-to-cypher/plan.md), D10 et D13). Les quotas de Vertex bornent la vitesse de dépense.

## Conséquences

- ✅ Une vue à tout moment (`/google-facture`, e-mails par palier) et un arrêt sans intervention humaine.
- ✅ Seul Vertex s'arrête : la base de référence, son réveil quotidien et les secrets ne sont pas touchés.
- ✅ Gratuit à cette échelle (paliers gratuits de Pub/Sub et Cloud Run), dans des services gérés ([ADR-0007](0007-infra-secrets-et-services-geres.md)).
- ⚠️ La coupure suit la dépense réelle avec quelques heures de retard : ce qui part entre-temps est facturé ; le plafond du banc, calculé en direct, couvre cet écart pour ses propres appels.
- ⚠️ Une fois coupée, l'API reste coupée : la réactiver est un geste volontaire, après relecture de la facture.
- ⚠️ 100 € jusqu'au 2026-12-31 : à revoir avant les jalons 3 et 4, ou en début d'année.

## Liens

- [Plan 002](../specs/002-agent-text-to-cypher/plan.md) : D10 (coût calculé), D13 (échecs et pannes), relevé de T0.2 (quotas, prix)
- [ADR-0002](0002-cadrage-environnement-cible-google-cloud.md) : environnement cible Google Cloud
- [ADR-0007](0007-infra-secrets-et-services-geres.md) : services gérés
- [ACCESS.md](../ACCESS.md) : budget, accès à Vertex
- Doc Google : [budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets), [spend cap budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps), lues le 2026-10-07
