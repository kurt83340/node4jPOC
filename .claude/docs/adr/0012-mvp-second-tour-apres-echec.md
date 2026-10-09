---
status: accepted
scope: mvp
phase: 2026-Q4
supersedes: null
---

# 0012 — Second tour d'une paire après un échec : faux d'office

**Statut :** Accepted
**Date :** 2026-10-09
**Décideur :** Julien Leroy

## Contexte

Deux questions du banc d'essai sont des seconds tours : Q18 se pose juste après Q2, Q28 juste après Q27, dans la même conversation. Elles mesurent la mémoire de conversation ([README des questions](../../../questions/README.md), règles de réponse). L'[ADR-0009](0009-mvp-protocole-mesure-techniques.md) compte faux un échec de l'agent (délai, nombre de tours ou budget dépassés) sans le relancer, et ne relance que les pannes d'infrastructure, la paire entière pour Q18 et Q28. Il ne dit pas ce que devient le second tour quand le premier échoue : la session est alors arrêtée, et Q18 (ou Q28) n'est jamais posée. La revue adverse de la phase 3 de la spec 002 l'a relevé le 2026-10-08. La règle vaut pour toutes les techniques des jalons 2 à 4.

## Options considérées

- **Option A — fausse d'office** : le second tour compte faux sans être posé ; une ligne d'échec à 0 s, avec une cause propre (le tour précédent en échec).
- **Option B — relancer la paire, comme une panne** : contraire à l'ADR-0009 ; un échec coûteux (un produit cartésien, un délai dépassé) sortirait du score.
- **Option C — poser le second tour dans une nouvelle session** : ne mesure plus la mémoire de conversation, qui est le but de Q18 et Q28.
- **Option D — retirer le second tour du score de la passe** : le nombre de questions notées varierait d'une technique à l'autre.
- **Option E — ne rien fixer** : chaque orchestration le compterait à sa façon, et le tableau comparatif mélangerait des règles.

## Décision

**Option A** (Julien, 2026-10-09). Quand le premier tour d'une paire échoue (Q2 ou Q27), le second (Q18 ou Q28) compte faux d'office : une ligne d'échec d'une durée nulle, sans tokens ni coût, avec une cause qui désigne le tour précédent en échec.

## Conséquences

- ✅ Le score de chaque technique porte sur les mêmes 30 questions. Un échec au premier tour coûte aussi le second, comme une technique sans mémoire de conversation échoue déjà logiquement à Q18 et Q28 (README).
- ✅ Aucun échec n'est relancé : la règle de l'ADR-0009 tient.
- ⚠️ Une paire pèse double : un seul échec coûte deux questions, à rappeler en lisant les scores par catégorie.
- ⚠️ À coder dans l'orchestration de la spec 002 (T4.3), avec une cause de plus dans `banc.mesures`.

## Liens

- [Plan 002](../specs/002-agent-text-to-cypher/plan.md) : D13, relevé de la revue adverse de la phase 3
- [ADR-0009](0009-mvp-protocole-mesure-techniques.md) : le protocole de mesure, que cet ADR précise sans le modifier
- [README des questions](../../../questions/README.md) : Q2, Q18, Q27, Q28 et la règle des conversations
