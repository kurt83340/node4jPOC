# Technique 2 — un agent qui écrit son Cypher, par le serveur MCP de Neo4j

Résultats de la [spec 002](../../.claude/docs/specs/002-agent-text-to-cypher/spec.md) (jalon 2), au 2026-10-11. Un
agent LLM reçoit la consigne et la fiche de schéma communes, puis répond aux 30 questions du banc d'essai en
interrogeant le graphe par `neo4j-mcp` v1.6.0, en lecture seule. Trois cellules séparent l'effet du client de celui du
modèle : Claude Code + Claude Sonnet 5.5, ADK + Claude Sonnet 5.5, ADK + Gemini 3.8 Flash.

Données : `banc/mesures/fr-1.csv` (3 passes comptées des trois cellules), `en-1.csv` (schéma anglais) et
`fr-controle.csv` (passe de contrôle), notés après la revue de `banc/mesures/revues.toml`. Protocole :
[ADR-0009](../../.claude/docs/adr/0009-mvp-protocole-mesure-techniques.md), amendé par
[ADR-0011](../../.claude/docs/adr/0011-infra-claude-par-api-anthropic.md) (Claude par l'API Anthropic),
[ADR-0014](../../.claude/docs/adr/0014-mvp-revue-assistee.md) (revue assistée) et
[ADR-0015](../../.claude/docs/adr/0015-mvp-source-du-tour-precedent.md) (source d'un second tour). Relevés détaillés :
[plan 002](../../.claude/docs/specs/002-agent-text-to-cypher/plan.md), D7 et D8.

## L'essentiel

- **Un agent text-to-Cypher bien outillé répond juste à presque tout.** Avec Claude Sonnet 5.5, 27,5 et 27,8 sur 30,
  99 % de sources vérifiées sur la trace, une réponse médiane en 6 à 7 secondes, pour 0,67 à 0,88 $ les 30 questions.
- **Le modèle compte, le client presque pas.** À modèle égal, Claude Code et ADK font jeu égal (0,3 point d'écart). À
  client égal, Gemini 3.8 Flash perd 7 points (20,7). Ce n'est pas qu'il se trompe : sur ses 63 réponses, 61 sont
  justes et 2 partielles. Il échoue 27 fois sur 90, dont 24 parce qu'il n'a pas conclu en 10 appels au modèle.
- **Un schéma aux identifiants anglais n'apporte rien de mesurable** à Gemini : 19,2 contre 20,7, un écart de −1,5,
  sous le seuil de 2,5 fixé avant la mesure ; la passe de contrôle française (21,5) écarte une dérive du modèle.
- **La faiblesse commune : les questions sémantiques**, où la réponse dépend du texte libre des descriptions (2 à 3,3
  sur 5). Les questions de faits et d'agrégats sont parfaites dans les trois cellules.

## Pour le tableau comparatif

| Cellule                  | Réponse juste, sur 30 (passes) | Sources citées    | Temps de réponse, médiane | Coût des 30 questions |
| ------------------------ | ------------------------------ | ----------------- | ------------------------- | --------------------- |
| Claude Code + Sonnet 5.5 | **27,5** (27,5 · 27,5 · 27,5)  | 99 % (86 sur 87)  | 7,3 s                     | 0,88 $                |
| ADK + Sonnet 5.5         | **27,8** (28 · 28 · 27,5)      | 99 % (86 sur 87)  | 6,2 s                     | 0,67 $                |
| ADK + Gemini 3.8 Flash   | **20,7** (19,5 · 22 · 20,5)    | 100 % (63 sur 63) | 14,2 s                    | 0,98 $                |

- **Réponse juste** : les justes, plus la moitié des partielles, après revue ; un échec compte faux (ADR-0009).
- **Sources citées** : part des réponses dont la source citée est vérifiée sur la trace (une requête exécutée pendant
  le tour, ou le tour précédent d'un second tour, dont le résultat porte la réponse) ; Q10 en est exemptée. Gemini
  cite juste chaque fois qu'il répond, mais il ne répond qu'à 63 questions sur 90.
- **Coût** : la moyenne d'une passe, calculée sur les tokens (`banc/prix.toml`) et recoupée avec les factures (§ Coût).
- **Effort de mise en place** : le même pour les trois cellules (§ Effort).

## Scores par catégorie

Moyenne des 3 passes, sur 5 ([ADR-0006](../../.claude/docs/adr/0006-mvp-banc-essai-30-questions.md)) :

| Catégorie                             | Claude Code | ADK + Claude | ADK + Gemini |
| ------------------------------------- | ----------- | ------------ | ------------ |
| Faits (Q4, Q21 à Q24)                 | 5           | 5            | 5            |
| Agrégats (Q12 à Q14, Q20, Q25)        | 5           | 5            | 5            |
| Parcours (Q1, Q5 à Q7, Q15)           | 4,5         | 4,5          | 3,33         |
| Raisonnement (Q2, Q11, Q18, Q27, Q28) | 5           | 5            | 2,33         |
| Robustesse (Q8, Q10, Q19, Q29, Q30)   | 5           | 5            | 3            |
| Sémantique (Q3, Q9, Q16, Q17, Q26)    | 3           | 3,33         | 2            |

Écart entre la meilleure et la moins bonne passe : 0 pour Claude Code, 0,5 pour ADK + Claude, 2,5 pour ADK + Gemini.

## Ce qui coûte des points

- **Gemini ne conclut pas** : 27 échecs, chacun faux d'office. 24 fois, il épuise ses 10 appels au modèle sur des
  requêtes valides, sans jamais rendre sa réponse : Q2, Q7, Q9, Q10, Q17 et Q26 à chaque passe, Q1, Q8, Q28 et Q30
  parfois. 3 fois, Q18 compte faux parce que Q2, son premier tour, a échoué (ADR-0012). Il appelle le modèle 5,5 fois
  par question en moyenne, contre 1,8 à 2 pour Claude. Le plafond de 10 appels vaut pour toutes les cellules (choix
  de Julien au pilote : plus d'appels aurait coûté plus et rendu la mesure moins comparable aux jalons 3 et 4).
- **Les partielles de Claude** (15 pour Claude Code, 13 pour ADK) tiennent à deux causes :
  - Q1 : des capacités Z, qu'aucun Pokémon n'apprend et que la règle exclut, citées parmi les attaques, le plus
    souvent en tête (« Hurlement des Roches-Lames »), dans les trois cellules ;
  - les questions sémantiques Q3, Q9, Q16, Q17 et Q26 : rappel incomplet, espèces écartées citées, ou espèces hors de
    la table de classement non prouvées par leur description.
- **Introspection** : la fiche suffit. Aucune lecture du schéma par Claude ; une seule par Gemini, sur 90 questions.

## Temps de réponse

Du message posé à la réponse finale, sur les seules réponses :

| Cellule                  | Médiane | 90 % des réponses en moins de | Plus longue |
| ------------------------ | ------- | ----------------------------- | ----------- |
| Claude Code + Sonnet 5.5 | 7,3 s   | 20,1 s                        | 129,5 s     |
| ADK + Sonnet 5.5         | 6,2 s   | 17,0 s                        | 72,6 s      |
| ADK + Gemini 3.8 Flash   | 14,2 s  | 37,3 s                        | 129,9 s     |

Chez Claude, les plus longues sont toutes à Q2, qui demande d'analyser une équipe de six Pokémon. Gemini échoue à
chaque Q2 ; sa plus longue est un Q8, une similarité de répertoires calculée sur tout le graphe.

## Coût

| Cellule                  | 3 passes | Par passe | Par question |
| ------------------------ | -------- | --------- | ------------ |
| Claude Code + Sonnet 5.5 | 2,635 $  | 0,878 $   | 0,029 $      |
| ADK + Sonnet 5.5         | 2,023 $  | 0,674 $   | 0,022 $      |
| ADK + Gemini 3.8 Flash   | 2,943 $  | 0,981 $   | 0,033 $      |

- **Gemini Flash coûte plus que Sonnet** malgré un prix au token plus bas : il appelle le modèle près de trois fois
  plus, et ses échecs épuisent leurs 10 appels.
- **Claude Code coûte plus qu'ADK** pour le même modèle : il écrit plus en cache (394 737 tokens contre 281 385 sur
  les 3 passes) et produit plus de sortie (145 305 tokens contre 118 799). Son petit modèle n'a rien coûté ici.
- **Recoupé avec les factures** (T9.3) : pour Claude, la Console Anthropic affiche 6,45 $ sur trente jours, pour
  6,450 $ calculés (sondes, répétition, pilote et `fr-1`) ; pour Gemini, l'export de facturation BigQuery compte les
  tokens de `fr-1` à l'unité près, 2,590 € net, soit 2,943 $ pour 2,943 $ calculés. Les coûts de `en-1` (2,76 $) et
  de `fr-controle` (0,90 $) restent à recouper dans l'export.
- **Toute la spec** a coûté environ 14,0 $ de LLM (Claude 6,45 $, Gemini 7,51 $), sous le budget de 35 $.

## Schéma anglais (FR/EN)

L'hypothèse laissée ouverte par l'[ADR-0005](../../.claude/docs/adr/0005-mvp-conventions-nommage-schema.md) : un LLM
écrit-il mieux son Cypher quand les labels, types et propriétés du graphe sont en anglais ? Mesurée sur ADK + Gemini, la
même instance basculée en anglais puis revenue, valeurs inchangées, prouvée à l'aller comme au retour
(plan 002, D8).

| Mesure                           | Passe 1 | Passe 2 | Passe 3 | Moyenne |
| -------------------------------- | ------- | ------- | ------- | ------- |
| Français, `fr-1`                 | 19,5    | 22      | 20,5    | 20,67   |
| Anglais, `en-1`                  | 19,5    | 19,5    | 18,5    | 19,17   |
| Contrôle français, `fr-controle` | 21,5    |         |         | 21,5    |

- **Verdict**, selon les règles fixées au pilote, avant toute passe comptée : la passe de contrôle tombe dans
  [18,5 ; 23], donc le modèle n'a pas dérivé entre les mesures ; l'écart vaut −1,5, sous le seuil de 2,5 (le bruit
  entre les passes françaises, ou 2 points au moins). **Pas d'effet mesurable du schéma anglais à cette taille.**
- **Hors verdict** : deux questions basculent, Q8 et Q27, justes au moins deux fois sur trois en français et fausses
  deux fois sur trois en anglais, chaque fois par des appels épuisés ; le recul anglais tient au raisonnement (2,33 → 1,33) et à la robustesse (3 → 2,33) ; les
  échecs « tours » ne baissent pas (24 → 25) : un schéma en anglais n'aide pas Gemini à conclure.
- **Effet de bord** : `db.propertyKeys()` garde les noms de clés que plus rien ne porte ; aucun agent anglais ne l'a
  appelée. À revoir avant qu'Aura Agent lise le schéma (jalon 4).

## Effort de mise en place

**Pour l'agent lui-même**, ce qu'il faut assembler :

- le serveur MCP officiel, `neo4j-mcp` v1.6.0 : un binaire, réglé en lecture seule par variables d'environnement,
  lancé par un script de 71 lignes qui lit les identifiants dans Secret Manager et masque l'identifiant de l'instance ;
- un client qui parle MCP : Claude Code, par une configuration, ou un agent ADK, par un `McpToolset` ;
- l'accès au modèle : une clé de l'API Anthropic, ou Vertex pour Gemini ;
- la consigne (9 lignes) et surtout la fiche de schéma (116 lignes : modèle, règles, valeurs possibles, 8 exemples).
  C'est le vrai travail de la technique : écrite avant toute mesure (T1.2), vérifiée sur la base le 2026-10-10 (T7.3,
  trois corrections), testée pour qu'elle ne souffle aucune réponse des 30 questions. C'est aussi ce qui rend
  l'introspection inutile.

Côté code, l'agent tient en peu de chose : une configuration pour Claude Code, un `McpToolset` pour ADK. Le temps passé
à les monter n'a pas été mesuré à part du banc.

**Pour le mesurer**, c'est le banc qui pèse : le harnais `banc/` (7 124 lignes de Python, 1 481 tests), 15 PR du
2026-10-07 au 2026-10-11 (dont 2 d'outillage : la CI et la coupure automatique de Vertex), la conception validée le
2026-10-01. Ce coût est celui du banc, réutilisable aux jalons 3 et 4, pas celui de la technique. La revue des
réponses, prévue à 3 h 30 pour Julien, est devenue assistée (ADR-0014) : il revoit seul 8 cas tirés au sort, puis
valide la pré-analyse de Claude.

## Limites

- **Une seule taille** : 30 questions, 3 passes, un modèle par fournisseur (Sonnet 5.5, Gemini 3.8 Flash), effort
  « high » ; le verdict du FR/EN ne vaut que pour Gemini 3.8 Flash.
- **Un plafond commun** de 10 appels au modèle par question : il pèse sur Gemini, qui conclut tard.
- **Une revue assistée** : décisions de Julien sur la pré-analyse de Claude. Ses contre-épreuves à l'aveugle donnent
  7 accords sur 8 pour les notes dans les deux campagnes de la phase 10, chaque désaccord portant sur Q1. Dans les
  cellules Claude, Claude pré-analyse des réponses de Claude ; l'aveugle masque la cellule, pas le style.
- **Des coûts partiellement recoupés** : `en-1` et `fr-controle` attendent l'export de facturation.

## Reproduire

```bash
uv run --directory banc python -m banc rapport --campagne fr-1 --complet         # scores, issues, coût, temps
uv run --directory banc python -m banc rapport --campagne en-1 --complet         # schéma anglais
uv run --directory banc python -m banc rapport --campagne fr-controle --complet  # passe de contrôle
uv run --directory banc python -m banc revoir --campagne fr-1 --verifier         # aucun cas restant
```

Les traces brutes (`logs/banc/`) restent sur le poste ; les mesures et les décisions sont versionnées.
