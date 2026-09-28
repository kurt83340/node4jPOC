# Cadrage — node4jPOC

> Ce dossier contient **tout ce qui sert à comprendre/définir le projet** + ses évolutions.
> Ce README est la **synthèse vivante** ; le détail brut est dans `tickets/`, `documents/`, `reunions/`.
>
> ⚠️ **Document vivant** : MAJ à chaque nouvelle réunion, ticket, pivot, accès accordé.
> Si pivot demandé par hiérarchie → réunion dans `reunions/YYYY-MM-DD-pivot.md` + MAJ ce README.

**Date kickoff :** 2026-09-28
**Demandeur :** Julien Leroy — ingénieur, projet perso (seul sur le projet)
**Canal initial :** brief écrit → [documents/2026-09-28-brief-poc.md](documents/2026-09-28-brief-poc.md) (texte intégral)
**Tickets liés :** aucun
**Docs reçus :** voir [documents/](documents/)

## Interlocuteurs

| Nom          | Rôle                               | Contact | Pour quoi            |
| ------------ | ---------------------------------- | ------- | -------------------- |
| Julien Leroy | Demandeur, décideur et développeur | —       | Toutes les décisions |

**Décisionnaire final :** Julien Leroy
**Cadence :** au fil des sessions de travail — reprise via [HANDOFF](../HANDOFF.md)

## Demande exprimée (verbatim)

> Je suis ingénieur et je travaille seul sur ce projet perso. Objectif : monter en compétence sur l'écosystème agentique de Neo4j en construisant un POC. Aucune stack n'est choisie : on explore les meilleures techniques, et c'est le POC qui dira lesquelles valent le coup. Explique tes choix au fur et à mesure : je veux apprendre, pas seulement obtenir du code.
>
> Un seul jeu de données, 10 questions de référence, et plusieurs techniques comparées sur ces mêmes questions […]
>
> Livrable final : un tableau comparatif qui croise chaque technique et chaque question, avec ces critères : réponse juste, sources citées, temps de réponse, coût, effort de mise en place.
>
> — Source : brief du 2026-09-28 ([texte intégral](documents/2026-09-28-brief-poc.md))

## Pivot 2026-09-28 — Environnement cible Google Cloud

**Avant** : POC neutre ; les briques Google Cloud étaient hors périmètre (brief).
**Après** : POC transposable à une entreprise full Google Cloud. Entrent au périmètre : Gemini Enterprise, CDC → Pub/Sub, Aura Graph Analytics ; Virtual Graph en option si son prix horaire se confirme. dbt reste hors POC. Découpage en 6 jalons ([ROADMAP](../ROADMAP.md)).
**Raison** : l'entreprise de Julien est full GCP avec dbt ; il veut un setup transposable, même s'il coûte un peu.
**Décideur** : Julien Leroy
**CR pivot** : [reunions/2026-09-28-pivot.md](reunions/2026-09-28-pivot.md) · [ADR-0002](../adr/0002-cadrage-environnement-cible-google-cloud.md)

## Le banc d'essai

**Techniques comparées**, sur les mêmes données et les mêmes questions :

1. **Cypher à la main** : modèle et requêtes écrits à la main. Sert aussi de **vérité de référence** pour les autres techniques.
2. **Agent text-to-Cypher via MCP** : serveur officiel `neo4j/mcp` ou « MCP for Aura » hébergé, branché sur un client MCP (Claude Code, n8n, ADK…).
3. **GraphRAG** : recherche vectorielle dans les descriptions en français, puis parcours du graphe pour le contexte.
4. **Aura Agent** : l'agent géré de Neo4j, généré à partir du schéma, exposé en MCP ou en REST.
5. _(option)_ **Mémoire d'agent** : `neo4j-agent-memory` (expérimental).

**Critères du tableau final :** réponse juste · sources citées · temps de réponse · coût · effort de mise en place.

**Questions de référence** (3 sur 10 définies, à compléter au jalon 1) :

| #   | Question                                                            | Réponse attendue                       | Technique visée           |
| --- | ------------------------------------------------------------------- | -------------------------------------- | ------------------------- |
| Q1  | « Quelles attaques font le plus mal à Dracaufeu ? »                 | Roche ×4, car Dracaufeu est Feu et Vol | Cypher                    |
| Q2  | « Propose une équipe de 6 qui couvre les faiblesses de la mienne. » | à établir en Cypher (jalon 1)          | agent en plusieurs étapes |
| Q3  | « Quel Pokémon vit près des volcans ? »                             | à établir en Cypher (jalon 1)          | GraphRAG (descriptions)   |

## Contexte

- **Données** : PokéAPI, fichiers CSV publics ([data/v2/csv](https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv)), textes en français (`language_id = 5`). Faits chiffrés et sources : [conception/research.md](../conception/research.md).
- **Base** : AuraDB Free (Aura Agent en a besoin) ; repli sur Neo4j en local avec Docker.
- **Volume** : environ 10 000 nœuds et 113 000 relations (estimation).
- **Fréquence** : chargement ponctuel, par un script **réexécutable sans créer de doublons**.
- **Existant** : aucun, projet vierge (template claude-Setup v1.5.0).

## Contraintes

- **Budget** : projet perso, offres gratuites d'abord (AuraDB Free ; MCP for Aura est inclus dans l'offre Free). Le coût est aussi un critère mesuré du comparatif.
- **Sécurité** : identifiants Aura dans `.env` (gitignoré, lecture interdite à Claude par `settings.json`). Le mot de passe n'est jamais affiché ni committé.
- **Délai** : aucun fixé.
- **Hébergement** : AuraDB Free, qui se met en pause après 72 h sans activité puis est supprimée après 30 jours de pause.
- **Techniques** : aucune stack imposée, c'est le POC qui dira lesquelles valent le coup. Doc à jour vérifiée avant chaque bibliothèque (les versions du brief datent du 2026-09-26).
- **Licence** : PokéAPI sous BSD-3 ; l'univers Pokémon appartient à Nintendo, donc usage d'apprentissage perso uniquement.
- **Mode de travail** : expliquer chaque choix au fil de l'eau (objectif d'apprentissage) ; réponses en français.

## Ce qui N'EST PAS demandé (out of scope)

- ~~Les briques Google Cloud : agent Neo4j dans Gemini Enterprise ; Pub/Sub (passe par du CDC, réservé aux offres Enterprise) ; Aura Graph Analytics avec BigQuery.~~ Réintégrées au [pivot du 2026-09-28](#pivot-2026-09-28--environnement-cible-google-cloud).
- dbt : il relève de l'équation de l'entreprise, pas du POC (pivot du 2026-09-28).
- Graph Data Science for BigQuery (expérimental) et Spanner Graph (ce n'est plus Neo4j).

## Risques identifiés au kickoff

- **Limites d'AuraDB Free contradictoires** : 200 000 nœuds et 400 000 relations selon la FAQ, 50 000 et 175 000 selon la page produit. Noter la vraie limite à la création. Le graphe estimé (~113 000 relations) tient dans les deux, mais la marge devient faible sous 175 000 si le modèle grossit (formes alternatives…).
- **Pause puis suppression de l'instance Free** : le script de chargement réexécutable sert aussi de filet de sécurité.
- **Versions très récentes, doc en retard** : par exemple, les variables `NEO4J_MCP_*` de `neo4j/mcp` v1.6.0 ne sont pas encore documentées. Se fier aux notes de version.
- **Français** : l'embedder par défaut de `neo4j-graphrag` ne gère que l'anglais, il faudra un embedder multilingue (jalon 3).
- **Descriptions répétées d'un jeu à l'autre** : ces doublons peuvent fausser la recherche vectorielle.
- **Aura Agent sur Free** : lecture seule et pas d'historique de conversation, ce qui limite les questions en plusieurs tours.

## Suite

- [x] Brief rédigé et archivé (2026-09-28)
- [x] Pivot : environnement cible Google Cloud (2026-09-28)
- [ ] Instance AuraDB Free créée, vraie limite notée, identifiants dans `.env`
- [ ] Projet Google Cloud avec compte de facturation (avant le jalon 2)
- [x] Jalon 1 : chargement en Cypher pur ([ADR-0003](../adr/0003-mvp-chargement-cypher-pur.md)) et modèle espèce + formes ([ADR-0004](../adr/0004-mvp-modele-espece-formes.md)) décidés, plan validé (2026-09-28)

---

## Comment ce dossier est organisé

```
cadrage/
├── README.md         ← ce fichier (la synthèse vivante)
├── tickets/          ← tickets Jira/Linear/Asana reçus
├── documents/        ← docs client (PDF, Excel, captures)
├── reunions/         ← comptes-rendus de réunions (incl. pivots)
└── diagrams/         ← schémas business (ASCII + Excalidraw/SVG si gros)
```

**Le README synthétise** ; le reste contient le **matériel brut** pour traçabilité.

**Pour les diagrammes** : convention détaillée dans [diagrams/README.md](diagrams/README.md). En 2 mots : ASCII inline par défaut, Excalidraw + export SVG si gros.
