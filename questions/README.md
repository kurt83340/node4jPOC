# Banc d'essai — les 30 questions de référence

> Définies le 2026-09-29 (spec [001-socle-donnees](../.claude/docs/specs/001-socle-donnees/spec.md), tâche T1.1). Le brief en demandait 10 ; Julien a porté le banc à **30, en 6 catégories de 5**, pour qu'aucune technique ne soit jugée sur une ou deux questions seulement.
> Chaque question est posée **telle quelle** à toutes les techniques du banc d'essai ; la « technique visée » est celle qui devrait y briller.
> Les requêtes Cypher de référence et les réponses attendues sont dans `qNN.cypher` et `attendu/qNN.txt` (T7.1, 2026-10-01) ; `scripts/questions.sh --verifier` les rejoue en lecture seule. Le harnais du jalon 2 lit les questions dans `banc.toml` (texte posé, mode de notation, valeurs attendues, distracteurs), qu'un test garde cohérent avec ce README et `attendu/` (spec 002, T1.1). La liste des 1 025 espèces (`especes.cypher`, `attendu/especes.txt`), rejouée avec les questions, n'en est pas une : la notation s'en sert pour reconnaître une espèce citée hors de l'ensemble attendu (spec 002, T2.1). La colonne « Premier calcul » vient d'une analyse des CSV du commit PokéAPI `168b1e8` : elle prouve que la question a une réponse dans les données, elle ne fait pas foi.

**Équipe de référence (« la mienne » dans Q2 et Q18)** : Florizarre, Dracaufeu, Tortank, Pikachu, Ronflex, Lokhlass.

## 1. Faits simples (étalon)

| #   | Question                                                                | Technique visée | Premier calcul                                              |
| --- | ----------------------------------------------------------------------- | --------------- | ----------------------------------------------------------- |
| Q4  | Quels sont les types et les talents de Lucario, dont son talent caché ? | toutes          | Combat et Acier ; Impassible, Attention, Cœur Noble (caché) |
| Q21 | Qui est le plus rapide entre Dracaufeu et Tortank ?                     | toutes          | Dracaufeu (Vitesse 100 contre 78)                           |
| Q22 | Contre quel type les attaques Normal n'ont-elles aucun effet ?          | toutes          | Spectre                                                     |
| Q23 | Quelle est la catégorie de Dracaufeu ?                                  | toutes          | « Pokémon Flamme »                                          |
| Q24 | Quels sont le type, la puissance et la catégorie de l'attaque Séisme ?  | toutes          | Sol, 100, physique                                          |

## 2. Parcours et multi-sauts

| #   | Question                                                                                   | Technique visée | Premier calcul                                                                                                 |
| --- | ------------------------------------------------------------------------------------------ | --------------- | -------------------------------------------------------------------------------------------------------------- |
| Q1  | Quelles attaques font le plus mal à Dracaufeu ?                                            | Cypher          | Roche ×4 (Dracaufeu est Feu et Vol) ; Roc-Boulet et Fracass'Tête (150), Laser Météore (120), Lame de Roc (100) |
| Q5  | Quelles sont toutes les évolutions possibles d'Évoli ?                                     | text-to-Cypher  | 8 : Aquali, Voltali, Pyroli, Mentali, Noctali, Phyllali, Givrali, Nymphali                                     |
| Q6  | Quels sont les types de Méga-Dracaufeu X, et en quoi diffèrent-ils de ceux de Dracaufeu ?  | text-to-Cypher  | Feu et Dragon, contre Feu et Vol                                                                               |
| Q7  | Quels Pokémon peuvent apprendre Séisme et ne craignent pas du tout les attaques Électrik ? | text-to-Cypher  | 71 espèces de type Sol (seul type immunisé contre l'Électrik)                                                  |
| Q15 | Donne toute la famille d'évolution de Pikachu.                                             | text-to-Cypher  | Pichu, Pikachu, Raichu ; autour, 19 formes (Raichu d'Alola, Méga-Raichu X et Y, Pikachu costumés…)             |

## 3. Agrégations, négations, superlatifs

| #   | Question                                                                                     | Technique visée | Premier calcul                                                                      |
| --- | -------------------------------------------------------------------------------------------- | --------------- | ----------------------------------------------------------------------------------- |
| Q12 | Quel Pokémon a le plus de PV ?                                                               | text-to-Cypher  | Leuphorie (255), à égalité avec la forme Éthernatos Infinimax                       |
| Q13 | Quelle attaque de type Feu est apprise par le plus de Pokémon ?                              | text-to-Cypher  | Zénith (677, attaque de statut) ; Lance-Flammes (203) parmi les attaques offensives |
| Q14 | Quels Pokémon de type Feu ne peuvent apprendre aucune attaque de type Eau ?                  | text-to-Cypher  | 55 espèces                                                                          |
| Q20 | Si les attaques de type Roche disparaissaient, quels Pokémon perdraient le plus d'attaques ? | text-to-Cypher  | Tarinor et Tarinorme (15), puis Gigansel, Onix et Steelix (14)                      |
| Q25 | Quel type compte le plus de Pokémon ?                                                        | text-to-Cypher  | Eau (154), devant Normal (131) et Plante (127)                                      |

## 4. Sémantique (descriptions)

| #   | Question                                                                                | Technique visée       | Premier calcul                                                                     |
| --- | --------------------------------------------------------------------------------------- | --------------------- | ---------------------------------------------------------------------------------- |
| Q3  | Quel Pokémon vit près des volcans ?                                                     | GraphRAG              | 16 espèces citent « volcan » (Magmar, Camérupt, Heatran…)                          |
| Q9  | Quels Pokémon vivent dans les profondeurs de l'océan, et de quels types sont-ils ?      | GraphRAG + graphe     | 17 candidats (Lugia, Relicanth, Lanturn, Luminéon…), à trier                       |
| Q16 | Quel Pokémon est capable de faire le tour de la planète en moins d'une journée ?        | GraphRAG (paraphrase) | les descriptions de Dracolosse et de Scorvol parlent de « tour du monde », à trier |
| Q17 | Parmi les Pokémon de type Eau, lesquels sont décrits comme dangereux pour les humains ? | GraphRAG + filtre     | une dizaine de candidats (Léviator, Viskuse…), à trier                             |
| Q26 | Quels Pokémon passent la majeure partie de leur temps à dormir ?                        | GraphRAG              | Abra, Parecool, Spododo par mots-clés ; d'autres à trouver par le sens, à trier    |

## 5. Raisonnement et mémoire (agents)

| #   | Question                                                                                           | Technique visée           | Premier calcul                                                                         |
| --- | -------------------------------------------------------------------------------------------------- | ------------------------- | -------------------------------------------------------------------------------------- |
| Q2  | Propose une équipe de 6 qui couvre les faiblesses de la mienne.                                    | agent en plusieurs étapes | l'équipe de référence craint 10 types (Électrik, Roche, Plante, Combat…)               |
| Q11 | Pourquoi Carapuce encaisse-t-il mieux les attaques Feu que Bulbizarre ?                            | agent (explication)       | Feu ×0,5 contre Carapuce (Eau), ×2 contre Bulbizarre (Plante et Poison)                |
| Q18 | _(2e tour, juste après Q2)_ Et dans mon équipe, lequel est le plus vulnérable aux attaques Roche ? | mémoire de conversation   | Dracaufeu (×4)                                                                         |
| Q27 | Mon Pikachu doit battre un Tortank : quelle attaque lui conseilles-tu, et pourquoi ?               | agent                     | une attaque Électrik (×2 contre Eau) : Électacle ou Élecanon (120), Fatal-Foudre (110) |
| Q28 | _(2e tour, juste après Q27)_ Et si l'adversaire remplace Tortank par Onix ?                        | agent + mémoire           | piège : l'Électrik est sans effet (Onix est Roche et Sol) ; Surf (Eau, ×4)             |

## 6. Robustesse, honnêteté, algorithme de graphe

| #   | Question                                                                                                                      | Technique visée          | Premier calcul                                                        |
| --- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------ | --------------------------------------------------------------------- |
| Q8  | En dehors de sa propre famille d'évolution, quels Pokémon ont le répertoire d'attaques le plus proche de celui de Dracaufeu ? | Aura Graph Analytics     | Drattak, Dracolosse, Reshiram, Libégon, Groudon                       |
| Q10 | Quel est le Pokémon préféré de Sacha ?                                                                                        | toutes (honnêteté)       | aucune mention de Sacha dans les données                              |
| Q19 | Quels sont les types de Dracofeu ? _(faute de frappe voulue)_                                                                 | toutes (robustesse)      | Feu et Vol, en reconnaissant Dracaufeu                                |
| Q29 | Pourquoi Pikachu est-il de type Feu ?                                                                                         | toutes (prémisse fausse) | Pikachu est Électrik : l'agent doit corriger la prémisse              |
| Q30 | Quelle est la meilleure attaque ?                                                                                             | toutes (question vague)  | pas de réponse unique : l'agent demande un critère ou annonce le sien |

## Règles de réponse

- **« Pokémon » = espèce**, dans sa forme par défaut, sauf si la question nomme une forme (Q6). Une réponse qui ajoute des formes alternatives est acceptée si elle le signale (Q12, Q15).
- **« Apprendre » une attaque** = dans au moins un jeu, par n'importe quelle méthode (montée de niveau, CT, maître des capacités, œuf…) : c'est le sens de la relation `APPREND` du graphe, agrégée sur tous les jeux ([plan 001, D3](../.claude/docs/specs/001-socle-donnees/plan.md)). Q1, Q7, Q8, Q13, Q14, Q20, Q27 et Q28 en dépendent ; la fiche de schéma du jalon 2 le dira aux techniques.
- **Conversations** : Q18 se pose dans la même conversation, juste après Q2 ; Q28 juste après Q27. Une technique sans mémoire de conversation échoue logiquement à Q18 et Q28 : c'est une mesure, pas un bug (Aura Agent sur Free ne garde pas l'historique).
- **Q1** : le type Roche (×4), puis les attaques Roche les plus puissantes **qu'au moins un Pokémon peut apprendre** (les capacités Z, jamais apprises, sont exclues). Le classement suit puissance × multiplicateur ; la précision, affichée dans la réponse de référence, sert à juger l'explication.
- **Q2** : pas de réponse figée, une **requête de contrôle**. Pour chaque type d'attaque super efficace (×2 ou plus) contre au moins un Pokémon de l'équipe de référence, l'équipe proposée doit compter au moins un membre qui y résiste (×0,5 ou moins, immunité comprise). La requête renvoie les types non couverts : liste vide = équipe valide. 6 espèces distinctes.
- **Q3, Q9, Q16, Q17, Q26 (sémantiques)** : trois ensembles, fixés par une grille écrite avant le tri (décision de Julien le 2026-10-01, [ADR-0008](../.claude/docs/adr/0008-mvp-notation-questions-semantiques.md)) :
  - **obligatoire** : une description le dit explicitement, de l'espèce elle-même ;
  - **acceptable** : une notion voisine qu'un lecteur raisonnable accepterait ;
  - **écarté** : le mot y est, pas le sens (le verbe « laver » pour « lave », un trait du corps au lieu d'un habitat…).

  Règle commune (2026-10-01) : un acceptable touche le cœur de la question, au moins en partie ; sinon il est écarté. Un tour du monde sans durée ne répond pas à Q16 (« en moins d'une journée »), une attaque redoutable contre ses adversaires ne répond pas à Q17 (« pour les humains »).

  La requête de référence trouve les candidats par un filet de mots-clés en mots entiers, puis applique une table de classement explicite (espèce, ensemble, raison) : un nouveau candidat sort « à classer », une espèce classée qui n'est plus trouvée sort « plus trouvée ». Elle ne recopie aucun texte de description ([ADR-0001](../.claude/docs/adr/0001-mvp-jeu-de-donnees-pokeapi.md)).

  - **Notation** : au singulier (Q3, Q16), juste si la réponse cite au moins une espèce obligatoire ou acceptable et aucune hors ensemble, partiel si elle en mêle, faux sinon. Au pluriel (Q9, Q17, Q26), rappel (part des espèces obligatoires trouvées) et précision (part des espèces citées qui sont justes) : juste si la précision vaut 100 % et le rappel au moins 50 %. Q9 demande aussi les types (exacts, forme par défaut) ; Q17 filtre sur le type Eau (exact).
  - **Correction sur preuve** : une espèce hors ensemble, citée avec la description qui la justifie, est examinée avec la grille ; si elle la satisfait, la réponse compte juste et l'espèce entre dans la table, datée.

- **Q7** : ensemble exact sur les types. Les immunités dues à un talent (Paratonnerre, Absorbe-Volt, Motorisé) sont acceptées en plus si l'agent les signale comme telles.
- **Q7 et Q14 (longues listes, 71 et 55 espèces)** : la réponse peut donner la liste complète, ou le compte avec un extrait. Juste : la liste complète sans intrus, ou le compte exact avec un extrait sans intrus ; partiel : un extrait juste, sans liste complète ni compte exact. Un intrus, ou un compte sans aucune espèce, s'examine à la main (règle écrite avant le pilote du jalon 2, 2026-10-08).
- **Q8** : similarité de Jaccard sur les attaques apprises (formes par défaut), famille d'évolution exclue ; top 5 classé, avec une tolérance sur l'ordre quand les scores sont à moins de 0,01 (Groudon 0,484 face à Braségali 0,480 et à Typhlosion 0,476).
- **Q12** : Leuphorie ; Éthernatos Infinimax est accepté s'il est signalé comme une forme.
- **Q13** : Zénith, toutes catégories d'attaques confondues ; Lance-Flammes est accepté si l'agent précise qu'il ne compte que les attaques offensives.
- **Q27** : toute attaque Électrik puissante, avec l'explication (×2 contre l'Eau) ; la précision compte dans l'explication (Élecanon, en tête par la puissance, n'a que 50 %). **Q28** : l'agent doit signaler que l'Électrik est sans effet contre Onix ; Surf est attendu, une autre attaque ×4 ou ×2 est acceptée avec son explication.
- **Q10, Q29, Q30** (questions comportementales) : pas de requête Cypher, une règle. Q10 : « ce n'est pas dans les données » (la culture générale n'est acceptée que si l'agent précise qu'elle ne vient pas du graphe ; sans source, la réponse compte comme fausse). Q29 : corriger la prémisse. Q30 : demander un critère ou annoncer celui qu'on retient.

## Critères du tableau comparatif

Pour chaque technique × question : réponse juste · sources citées · temps de réponse · coût · effort de mise en place. Les scores s'agrègent par catégorie (par exemple « text-to-Cypher : 4/5 en multi-sauts, 1/5 en sémantique »).
