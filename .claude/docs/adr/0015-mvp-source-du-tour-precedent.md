---
status: accepted
scope: mvp
phase: 2026-Q4
supersedes: null
amends: 0009
---

# 0015 — Source d'un second tour : une requête du tour précédent compte

**Statut :** Accepted
**Date :** 2026-10-11
**Décideur :** Julien Leroy

## Contexte

L'[ADR-0009](0009-mvp-protocole-mesure-techniques.md) définit la source citée : « une requête exécutée pendant le tour, dont le résultat contient la réponse, ou une description renvoyée pendant le tour ». Deux questions du banc se posent au second tour d'une paire, dans la même conversation que leur tour précédent : Q18 après Q2, Q28 après Q27 ([ADR-0012](0012-mvp-second-tour-apres-echec.md)). Elles mesurent ce que l'agent garde de la conversation.

Dans la revue de `fr-1` (T9.2, [plan 002, D7](../specs/002-agent-text-to-cypher/plan.md)), Q28 a reçu la source « oui » quand les chiffres de Surf venaient d'une requête du tour précédent (Q27), contre la lettre de l'ADR-0009. L'audit doc-health du 2026-10-11 l'a relevé : la règle doit trancher, pour la phase 10 et pour les jalons 3 et 4, qui reprennent ce protocole.

Q28 se note en revue (`notation = "revue"`) : la règle s'y applique à la revue. Q18 se note automatiquement (`notation = "valeur"`), et `banc.notation` ne cherche sa source que dans le tour courant : dans `fr-1`, une réponse de Q18 a la source « non » ainsi.

## Options considérées

- **Option A — Amender l'ADR-0009 sur ce point** : au second tour d'une paire, une requête du tour précédent de la même conversation compte comme source.
- **Option B — Une précision datée au plan 002** : plus légère, mais la règle vivrait dans une spec, alors que le protocole sert aussi aux jalons 3 et 4.
- **Option C — L'ADR-0009 à la lettre** : repasser à « non » la source des Q28 de `fr-1` ; contraire au but des seconds tours, qui mesurent la mémoire de la conversation.
- **Option D — Ne rien faire** : `fr-1` resterait en écart à l'ADR, et chaque revue future trancherait au cas par cas.

## Décision

**Option A** (Julien, 2026-10-11 : « ok », sur la préférence de Claude). Elle remplace dans l'ADR-0009 le point « Source citée : une requête exécutée pendant le tour » pour les seconds tours : **au second tour d'une paire, une requête exécutée au tour précédent de la même conversation compte aussi comme source, si son résultat contient la réponse**. Pour toutes les autres questions, la règle de l'ADR-0009 tient.

- **Q28** (revue) : appliquée dès la revue de la campagne anglaise `en-1` ; `fr-1` l'appliquait déjà.
- **Q18** (note automatique) : `banc.notation` lira aussi le tour précédent. Le changement attend la fin de la phase 10, hors de toute campagne (T11.0), pour que `fr-1`, `en-1` et la passe de contrôle soient notées de la même façon. La colonne source de leurs Q18 est ensuite recalculée d'un coup, avant le rapport (T11.1).

## Conséquences

- ✅ Les seconds tours sont jugés sur ce qu'ils mesurent : la mémoire de la conversation, requêtes comprises.
- ✅ La revue de `fr-1` rejoint la règle écrite ; les jalons 3 et 4 la trouvent dans le protocole, pas dans une spec.
- ✅ Le verdict du FR/EN n'en dépend pas : il compte les scores (justes, plus la moitié des partielles), pas la source.
- ⚠️ Jusqu'à T11.0, la note automatique de Q18 suit l'ancienne règle, dans les trois campagnes de la phase 10 ; le rapport ne doit pas lire leur colonne source avant le recalcul.
- ⚠️ Une requête du tour précédent peut porter une réponse que l'agent n'a pas relue : la règle exige que son résultat contienne la réponse, comme pour le tour courant.

## Liens

- [ADR-0009](0009-mvp-protocole-mesure-techniques.md) (point remplacé), [ADR-0012](0012-mvp-second-tour-apres-echec.md) (seconds tours), [ADR-0014](0014-mvp-revue-assistee.md) (revue assistée)
- [Plan 002](../specs/002-agent-text-to-cypher/plan.md) : D4 (notation), D7 (revue de `fr-1`) ; [tâches](../specs/002-agent-text-to-cypher/tasks.md) : T11.0
