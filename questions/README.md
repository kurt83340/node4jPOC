# Banc d'essai — les 30 questions de référence

> Définies le 2026-09-29 (spec [001-socle-donnees](../.claude/docs/specs/001-socle-donnees/spec.md), tâche T1.1). Le brief en demandait 10 ; Julien a porté le banc à **30, en 6 catégories de 5**, pour qu'aucune technique ne soit jugée sur une ou deux questions seulement.
> Chaque question est posée **telle quelle** à toutes les techniques du banc d'essai ; la « technique visée » est celle qui devrait y briller.
> Les requêtes Cypher de référence et les réponses attendues (`qNN.cypher`, `attendu/qNN.txt`) arrivent en T7.1, une fois les données chargées. La colonne « Premier calcul » vient d'une analyse des CSV du commit PokéAPI `168b1e8` : elle prouve que la question a une réponse dans les données, elle ne fait pas foi.

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
| Q20 | Si les attaques de type Roche disparaissaient, quels Pokémon perdraient le plus d'attaques ? | text-to-Cypher  | Tarinor et Tarinorme (15), puis Onix et Steelix (14)                                |
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
- **Conversations** : Q18 se pose dans la même conversation, juste après Q2 ; Q28 juste après Q27. Une technique sans mémoire de conversation échoue logiquement à Q18 et Q28 : c'est une mesure, pas un bug (Aura Agent sur Free ne garde pas l'historique).
- **Q1** : le type Roche (×4), puis les attaques Roche les plus puissantes **qu'au moins un Pokémon peut apprendre** (les capacités Z, jamais apprises, sont exclues).
- **Q2** : pas de réponse figée, une **requête de contrôle**. Pour chaque type d'attaque super efficace (×2 ou plus) contre au moins un Pokémon de l'équipe de référence, l'équipe proposée doit compter au moins un membre qui y résiste (×0,5 ou moins, immunité comprise). La requête renvoie les types non couverts : liste vide = équipe valide. 6 espèces distinctes.
- **Q3, Q9, Q16, Q17, Q26** : un ensemble **obligatoire** (les espèces dont une description le dit explicitement) et un ensemble **acceptable** (formulations proches), triés à la main en T7.1 pour écarter les faux positifs (le verbe « laver » pour « lave », par exemple).
- **Q7** : ensemble exact sur les types. Les immunités dues à un talent (Paratonnerre, Absorb Volt, Motorisé) sont acceptées en plus si l'agent les signale comme telles.
- **Q8** : similarité de Jaccard sur les attaques apprises (formes par défaut), famille d'évolution exclue ; top 5 classé, avec une tolérance sur l'ordre quand les scores sont à moins de 0,01 (Groudon 0,484 face à Braségali 0,480).
- **Q12** : Leuphorie ; Éthernatos Infinimax est accepté s'il est signalé comme une forme.
- **Q13** : Zénith, toutes catégories d'attaques confondues ; Lance-Flammes est accepté si l'agent précise qu'il ne compte que les attaques offensives.
- **Q27** : toute attaque Électrik puissante, avec l'explication (×2 contre l'Eau). **Q28** : l'agent doit signaler que l'Électrik est sans effet contre Onix ; Surf est attendu, une autre attaque ×4 ou ×2 est acceptée avec son explication.
- **Q10, Q29, Q30** (questions comportementales) : pas de requête Cypher, une règle. Q10 : « ce n'est pas dans les données » (la culture générale n'est acceptée que si l'agent précise qu'elle ne vient pas du graphe ; sans source, la réponse compte comme fausse). Q29 : corriger la prémisse. Q30 : demander un critère ou annoncer celui qu'on retient.

## Critères du tableau comparatif

Pour chaque technique × question : réponse juste · sources citées · temps de réponse · coût · effort de mise en place. Les scores s'agrègent par catégorie (par exemple « text-to-Cypher : 4/5 en multi-sauts, 1/5 en sémantique »).
