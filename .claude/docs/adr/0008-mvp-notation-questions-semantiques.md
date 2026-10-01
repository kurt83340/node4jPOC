---
status: accepted
scope: mvp
phase: 2026-Q4
supersedes: null
---

# 0008 — Notation des questions sémantiques : grille, trois ensembles, cœur de la question

**Statut :** Accepted
**Date :** 2026-10-01
**Décideur :** Julien Leroy

## Contexte

Cinq des trente questions du banc d'essai ([ADR-0006](0006-mvp-banc-essai-30-questions.md)) sont sémantiques : Q3 (volcans), Q9 (profondeurs de l'océan), Q16 (tour de la planète en moins d'une journée), Q17 (type Eau dangereux pour les humains) et Q26 (dormir la majeure partie du temps). Leur réponse se lit dans les descriptions, en langue naturelle : pas de réponse exacte, et le README prévoyait seulement des ensembles « triés à la main ». Cette notation servira à comparer toutes les techniques des jalons 2 à 4 : elle doit être robuste, rejouable et la même pour toutes (T7.1 de la spec 001).

## Options considérées

- **Option A — Mots-clés seuls** : la référence est l'ensemble des espèces dont une description contient le mot (« 16 espèces citent volcan »). Simple et rejouable, mais confond le mot et le sens : « il se lave », « son corps contient du magma ».
- **Option B — Tri à la main, au cas par cas** : juste sur le moment, mais subjectif, non rejouable, et muet quand les données changent.
- **Option C — Juge LLM** : une IA classe chaque réponse. Rapide, mais ajoute un biais et un coût au banc d'essai même qui compare des techniques fondées sur des LLM.
- **Option D — Grille, filet et table de classement** (détail ci-dessous).
- **Option E — Ne rien faire** : garder « triés à la main » ; la notation des jalons 2 à 4 resterait arbitraire.

## Décision

**Option D** (Julien, 2026-10-01) :

- **Une grille écrite avant le tri**, par question, qui définit trois ensembles : **obligatoire** (une description le dit explicitement, de l'espèce elle-même), **acceptable** (une notion voisine qu'un lecteur raisonnable accepterait), **écarté** (le mot y est, pas le sens).
- **Une règle commune** : un acceptable touche le cœur de la question, au moins en partie ; sinon il est écarté. Un tour du monde sans durée ne répond pas à Q16, une attaque redoutable contre ses adversaires ne répond pas à Q17.
- **Une requête rejouable** : un filet de mots-clés en mots entiers trouve les candidats, une table explicite (espèce, ensemble, raison) les classe. Un nouveau candidat sort « à classer », une espèce qui n'est plus trouvée sort « plus trouvée » : tout changement des données ou du filet se voit au rejeu.
- **Une notation fixée d'avance** : au singulier (Q3, Q16), juste si la réponse cite au moins une espèce obligatoire ou acceptable et aucune hors ensemble, partiel si elle en mêle, faux sinon ; au pluriel (Q9, Q17, Q26), rappel sur les obligatoires et précision sur les espèces citées, juste si la précision vaut 100 % et le rappel au moins 50 %.
- **Une correction sur preuve** : une espèce hors ensemble, citée avec la description qui la justifie, est examinée avec la grille ; si elle la satisfait, la réponse compte juste et l'espèce entre dans la table, datée.

## Conséquences

- ✅ Rejouable et versionné : `scripts/questions.sh --verifier` confronte chaque table à la base.
- ✅ Les pièges restent dans les tables, écartés avec leur raison (Arcanin et ses 10 000 km en 24 heures pour Q16) : ils révèlent la technique qui s'arrête au mot-clé.
- ✅ Un changement de données ne passe pas en silence (« à classer », « plus trouvée »).
- ⚠️ Le filet peut rater une formulation : la correction sur preuve, puis la recherche vectorielle du jalon 3, contrôlent ce qu'il manque.
- ⚠️ La grille reste un jugement humain : elle se corrige par une règle datée, appliquée à tous les candidats, jamais au cas par cas.
- ⚠️ Les seuils du pluriel (100 % de précision, 50 % de rappel) sont arbitraires : à revoir sur les premières mesures du jalon 2.
- ⚠️ Les tables ne recopient aucune description, seulement des noms et de courtes raisons ([ADR-0001](0001-mvp-jeu-de-donnees-pokeapi.md)).

## Liens

- [README des questions](../../../questions/README.md) : la méthode et la notation, en pratique
- [Plan de la spec 001, D11](../specs/001-socle-donnees/plan.md)
- [ADR-0006](0006-mvp-banc-essai-30-questions.md) : le banc d'essai, que cet ADR précise sans le remplacer
