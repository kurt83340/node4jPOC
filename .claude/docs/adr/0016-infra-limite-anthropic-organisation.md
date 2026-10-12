---
status: accepted
scope: infra
phase: 2026-Q4
supersedes: null
amends: 0011
---

# 0016 — Clé Anthropic dans « Default », bornée par la limite de l'organisation

**Statut :** Accepted
**Date :** 2026-10-12
**Décideur :** Julien Leroy

## Contexte

L'[ADR-0011](0011-infra-claude-par-api-anthropic.md) range la clé du banc dans un workspace dédié, avec sa propre limite mensuelle, et plafonne Claude par 20 $ de crédits prépayés, sans recharge automatique. Le 2026-10-11 (T9.3, [plan 002, D7](../specs/002-agent-text-to-cypher/plan.md)), Claude a lu la Console Anthropic à la demande de Julien. Elle montrait autre chose :

- aucun workspace dédié : l'organisation n'a que « Default » et « Claude Code », et la clé du banc (`julien-api-key`, secret `anthropic-api-banc`) est dans « Default », sans limite propre ;
- une limite mensuelle de l'organisation à 1 000 $ ;
- 31,61 $ de crédits, venus de deux crédits offerts de 30 $ (2026-04-02, valables jusqu'au 2027-04-03), sans aucun achat ; recharge automatique coupée ;
- une clé qui expire le 2026-11-07.

La vraie borne était donc le solde des crédits, plus le `--plafond-usd` de chaque campagne.

## Options considérées

- **Option A — Ramener la limite mensuelle de l'organisation de 1 000 à 20 $**, pour toutes ses clés ; la clé reste dans « Default ».
- **Option B — Un workspace dédié limité à 20 $, avec une nouvelle clé** : la lettre de l'ADR-0011, mais plus long, et la nouvelle clé passe par Julien jusqu'à Secret Manager.
- **Option C — Ne rien changer** : le solde des crédits (31,61 $) pour seule borne, plus le `--plafond-usd` des campagnes.

## Décision

**Option A** (Julien, 2026-10-11 : « go et do A », sur la préférence de Claude). Elle remplace dans l'ADR-0011 le workspace dédié et son plafond (« la clé d'un workspace dédié au banc », « 20 $ d'abord », « limite mensuelle du workspace ») : **la clé du banc reste dans le workspace « Default », et la dépense Claude est bornée par la limite mensuelle de l'organisation, 20 $, et par le solde des crédits, sans recharge automatique**. Le reste de l'ADR-0011 tient : Claude par l'API Anthropic, clé dans Secret Manager passée par l'environnement, Gemini sur Vertex `eu`.

Fait le 2026-10-11 par Claude dans la Console (Billing → Spend limits), vérifié après rechargement ; [ACCESS](../ACCESS.md) corrigé ; rappel d'expiration de la clé posé (premier e-mail le 2026-10-17, puis chaque semaine).

## Conséquences

- ✅ Une limite de 20 $ par mois pour toute l'organisation, en plus du solde des crédits et du `--plafond-usd` de chaque campagne.
- ✅ Ni nouvelle clé ni changement dans Secret Manager.
- ⚠️ La limite vaut pour toutes les clés de l'organisation : un autre usage partage les 20 $.
- ⚠️ La clé expire le 2026-11-07 : la renouveler avant, puis mettre à jour le secret `anthropic-api-banc` ([ACCESS](../ACCESS.md)).
- ⚠️ Les crédits offerts expirent le 2027-04-03.

## Liens

- [ADR-0011](0011-infra-claude-par-api-anthropic.md) (point remplacé), [ADR-0010](0010-infra-plafond-de-depense.md) (plafond Google)
- [Plan 002](../specs/002-agent-text-to-cypher/plan.md) : D7 (recoupement de T9.3, constat et décision) ; [ACCESS](../ACCESS.md) (clé, Console)
