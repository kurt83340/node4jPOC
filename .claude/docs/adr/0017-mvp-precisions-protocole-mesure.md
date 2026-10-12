---
status: accepted
scope: mvp
phase: 2026-Q4
supersedes: null
---

# 0017 — Précisions du protocole de mesure : plafonds invisibles, instructions du serveur ôtées, garde-fou, reprises

**Statut :** Accepted
**Date :** 2026-10-12
**Décideur :** Julien Leroy

## Contexte

L'[ADR-0009](0009-mvp-protocole-mesure-techniques.md) fixe le protocole de mesure du banc d'essai : même entrée pour toutes les techniques, un seul chemin vers la base en lecture seule, échec de l'agent contre panne. En le construisant pour le jalon 2, la spec 002 a dû trancher quatre points qu'il laisse ouverts. Julien les a choisis sur relevé des vrais clients (T4.1 à T4.3, le 2026-10-09 ; plafond confirmé au pilote, le 2026-10-10), et ils sont consignés au [plan 002](../specs/002-agent-text-to-cypher/plan.md) (D3, D13). Ils valent pour les jalons 3 et 4, qui réutilisent le banc : une règle du protocole ne doit pas vivre dans le plan d'une spec livrée (la raison qui a fait écarter l'option B de l'[ADR-0015](0015-mvp-source-du-tour-precedent.md)).

## Options considérées

- **Option A — Un ADR qui précise l'ADR-0009** sur ces quatre points, sans en remplacer aucun, comme l'[ADR-0012](0012-mvp-second-tour-apres-echec.md) l'a fait pour le second tour après un échec.
- **Option B — Les laisser au plan 002**, cité depuis le plan de chaque spec suivante : rien à écrire, mais la règle se cherche dans une spec livrée.
- **Option C — Ne rien faire** : chaque jalon les redécouvre ou les tranche autrement, et le tableau comparatif comparerait des protocoles.

## Décision

**Option A** (Julien, 2026-10-12 : texte validé tel quel, sur la proposition de Claude). Quatre règles s'ajoutent à l'ADR-0009 :

- **Plafonds invisibles de l'agent** : par question, 10 appels au modèle et 180 s ; par conversation, 0,50 $. La cellule les tient, l'agent ne les connaît pas : la consigne lui dit d'interroger le graphe « autant de fois qu'il le faut ». Le budget se compte sur le flux de l'API, jamais par une option du client qui afficherait à l'agent ce qui lui reste (`--max-budget-usd` de Claude Code le montre après chaque appel d'outil).
- **Une entrée réduite à la consigne, la fiche et les outils** : l'agent ne voit que l'outil de lecture du serveur (`read-cypher` ; `get-schema` masqué), et le lanceur ôte les instructions que le serveur envoie à la connexion (membre `instructions` de sa réponse à `initialize`) : elles citent un outil retiré, et un client les injecterait dans la conversation.
- **Garde-fou sur un gros résultat d'outil** : dans un client qui passe un résultat d'outil entier au modèle (ADK), un résultat dont le coût estimé (un token pour 3 caractères, au plus haut du prix de l'entrée ou de l'écriture en cache) ferait dépasser le budget de la conversation arrête le tour avant l'appel suivant : échec « budget », rien de dépensé en trop. Claude Code coupe lui-même un résultat au-delà de 25 000 tokens ; l'écart entre clients reste mesuré.
- **Reprises** : chaque client reprend au plus 2 fois un appel en échec (429, 5xx), comme le client Anthropic d'ADK par défaut, quand Claude Code en ferait 10 ; un délai dépassé pendant une reprise reste une panne (ADR-0009). Une panne rejoue la conversation entière, la paire comprise ; 3 pannes de suite sur une même conversation arrêtent la campagne ; plus de 2 pannes dans une série (une cellule, une passe) la rendent invalide, et le rapport tranche. La reprise d'une campagne interrompue note une conversation dont la trace est complète, sans jamais la rejouer : un échec ne se rejoue pas.

## Conséquences

- ✅ Les jalons 3 et 4 trouvent ces règles dans les décisions, pas dans le plan d'une spec livrée.
- ✅ Un échec mesure la technique, pas ce que l'agent sait de ses limites ; aucune technique ne règle son effort sur un budget affiché.
- ⚠️ Un agent qui ignore ses limites peut les épuiser sans conclure : 24 des 27 échecs de Gemini dans `fr-1` ([rapport de la technique 2](../../../banc/resultats/technique-2.md)). C'est mesuré, pas corrigé.
- ⚠️ Le garde-fou estime par excès : il peut arrêter un tour qui aurait tenu de justesse.
- ⚠️ Les techniques gérées du jalon 4 imposent leur client : leurs plafonds, leurs reprises et leurs instructions se relèvent et se notent comme un écart au protocole.

## Liens

- [ADR-0009](0009-mvp-protocole-mesure-techniques.md) (protocole, que cet ADR précise sans le remplacer) ; [ADR-0012](0012-mvp-second-tour-apres-echec.md) (même démarche)
- [Plan 002](../specs/002-agent-text-to-cypher/plan.md) : D3 (relevé T4.1), D13 (T4.2, T4.3) ; [tâches](../specs/002-agent-text-to-cypher/tasks.md) : T4.1 à T4.3, T8.1
