---
status: accepted
scope: mvp
phase: 2026-Q4
supersedes: null
---

# 0018 — Technique sans outil : consigne de contexte, source citée, encodage de la question

**Statut :** Accepted
**Date :** 2026-10-13
**Décideur :** Julien Leroy

## Contexte

L'[ADR-0009](0009-mvp-protocole-mesure-techniques.md) fixe le protocole du banc d'essai pour des techniques qui lisent la base par un outil : « même entrée pour tous » (une consigne et une fiche communes), « source citée » (une requête exécutée pendant le tour dont le résultat contient la réponse, ou une description renvoyée pendant le tour), temps à l'horloge monotone, coût en tokens × prix. Les [ADR-0012](0012-mvp-second-tour-apres-echec.md), [0015](0015-mvp-source-du-tour-precedent.md) et [0017](0017-mvp-precisions-protocole-mesure.md) l'ont précisé pour le jalon 2.

Le jalon 3 mesure un GraphRAG ([spec 003](../specs/003-graphrag-descriptions/spec.md)) : le harnais encode la question, cherche dans l'index vectoriel des descriptions par `read-cypher`, puis un seul appel au LLM rédige la réponse à partir du résultat. Le LLM n'a aucun outil. La conception (2026-10-12) et sa revue adverse (2026-10-13) ont relevé trois points où l'ADR-0009, écrit pour un agent, ne dit pas quoi faire :

- **Entrée** : `questions/consigne.md` dit d'interroger le graphe « avec l'outil `read-cypher` » et « autant de fois qu'il le faut » ; un LLM sans outil recevrait une consigne fausse.
- **Source** : `banc.notation` valide une description citée dès que l'enregistrement qui la porte contient une valeur juste, alors qu'une requête citée doit les porter toutes. Avec un contexte d'une entrée par espèce, citer n'importe quelle description de la bonne espèce validerait tout fait sur elle : le critère « sources » serait plus lâche que pour la technique 2.
- **Encodage** : la règle d'isolement interdit Vertex dans une cellule Claude ([plan 002](../specs/002-agent-text-to-cypher/plan.md), D3) ; l'encodage de la question se fait donc hors de la conversation, et son temps comme son coût sortent de la ligne mesurée.

## Options considérées

- **Option A — Un ADR qui précise l'ADR-0009** sur ces trois points, sans en remplacer aucun, comme l'ADR-0017.
- **Option B — Les laisser au plan 003** : rien à écrire ici, mais la règle se chercherait dans une spec, alors qu'Aura Agent (jalon 4) et toute technique sans outil la reprendront (raison qui a fait écarter la même option dans les ADR-0015 et 0017).
- **Option C — L'ADR-0009 à la lettre** : consigne d'agent donnée à un LLM sans outil, règle de source plus lâche que celle des requêtes, encodage dans le chrono au prix de la règle d'isolement.
- **Option D — Ne rien faire** : chaque technique sans outil se mesurerait à sa façon, et le tableau comparatif comparerait des protocoles.

## Décision

**Option A** (Julien, 2026-10-13, sur les préférences de Claude). Trois règles s'ajoutent à l'ADR-0009 pour une technique dont le LLM n'a pas d'outil :

- **Même entrée** : la même fiche de schéma, et une consigne de contexte (`questions/consigne-contexte.md`) : la consigne commune sans ce qui parle de l'outil, même rôle, même règle (la réponse vient du contexte, pas de la mémoire), même format de fin ; « Sources » y désigne les descriptions citées, avec leurs jeux. Texte validé par Julien ; mêmes tests de contamination que la consigne commune.
- **Source citée** : des descriptions citées valent source si elles ont été renvoyées pendant le tour (ou au tour précédent, au second tour d'une paire, ADR-0015) et si, réunies, les enregistrements qui les portent contiennent toutes les valeurs de la réponse : la rigueur d'une requête citée, pas une seule valeur. La règle vaut pour toutes les techniques dans le tableau comparatif : appliquée à la seule technique 3, elle la désavantagerait sur les questions au pluriel, où une seule description suffisait à la technique 2 ; la colonne source de `fr-1` est relue avec elle depuis les traces, en ajout daté au rapport de la technique 2 (les scores n'en dépendent pas).
- **Encodage de la question** : quand la question s'encode avant la conversation (même modèle, même texte, même vecteur), le harnais l'encode à la création de la campagne ; le temps mesuré l'exclut, et sa latence médiane se rapporte à côté du temps dans le rapport et le tableau comparatif ; son coût se compte par campagne (tokens × prix daté).

## Conséquences

- ✅ Le LLM sans outil reçoit une consigne vraie, et rien d'autre ne change de l'entrée commune.
- ✅ Le critère « sources » juge la technique 3 aussi strictement que la technique 2.
- ✅ La règle d'isolement des cellules tient : aucune cellule Claude n'appelle Vertex.
- ⚠️ « Même entrée » devient : même fiche, mêmes règles, même format de fin ; la consigne diffère par les seules phrases sur l'outil.
- ⚠️ Le temps de la technique 3 exclut l'encodage ; Aura Agent (jalon 4) comptera le sien dans son temps : le tableau met la latence de l'encodage à côté.
- ⚠️ Une réponse juste qui cite une description sans que les enregistrements cités portent toute la réponse a la source « non » : c'est voulu, et la revue assistée tranche les cas douteux (ADR-0014).
- ⚠️ Résidu : pour une réponse à une seule valeur, une description quelconque de la bonne espèce suffit encore, puisque son enregistrement porte toute l'espèce ; le rapport le dit.
- ⚠️ La colonne source de `fr-1` change de lecture : la première reste au rapport de la technique 2, la seconde s'y ajoute, datée.

## Liens

- [ADR-0009](0009-mvp-protocole-mesure-techniques.md) (protocole, que cet ADR précise sans le remplacer) ; [ADR-0015](0015-mvp-source-du-tour-precedent.md) (source d'un second tour) ; [ADR-0017](0017-mvp-precisions-protocole-mesure.md) (même démarche)
- [Plan 003](../specs/003-graphrag-descriptions/plan.md) : D5, D8, D9 ; [research 003](../specs/003-graphrag-descriptions/research.md) : revue adverse
