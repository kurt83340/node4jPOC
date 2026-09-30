# Changelog — node4jPOC

Format : [Keep a Changelog](https://keepachangelog.com/). Versionning : `vYYYY.MM.DD-HHMM` (tag de déploiement).

## [Unreleased]

### Added

- Initialisation du projet depuis le template claude-Setup v1.5.0 (2026-09-26)
- Page d'initiative du POC dans le [README](../../README.md) : objectif, pourquoi, vue d'ensemble, jalons, critères de réussite, périmètre, risques, décisions (2026-09-30)
- Schéma d'ensemble fait avec diagram-design : source [vue-ensemble.html](conception/diagrams/vue-ensemble.html) et export [vue-ensemble.png](conception/diagrams/vue-ensemble.png) côte à côte, en PNG parce que GitHub ne charge pas les polices d'un SVG affiché en image (2026-09-30)
- Suivi dans Jira, [projet NEO](https://frjulienleroy.atlassian.net/jira/software/projects/NEO/boards/40) (Kanban géré par l'équipe) : un epic par jalon (NEO-1 à NEO-4) ; pour le jalon 1, un ticket par phase de la spec 001, plus NEO-6 « Créer l'instance AuraDB Free » (NEO-5 à NEO-12) ; une story seulement quand il y a un résultat à montrer ; le dépôt fait foi (2026-09-30)
- [Dépôt GitHub privé](https://github.com/kurt83340/node4jPOC) `kurt83340/node4jPOC` relié à NEO par l'application GitHub for Atlassian : une clé de ticket dans un message de commit ou un titre de PR fait remonter le travail dans le ticket (2026-09-30)

### Changed

- Pivot 2026-09-28 : environnement cible Google Cloud, découpage en 6 jalons ([CR](cadrage/reunions/2026-09-28-pivot.md))
- [Règles git](../rules/git-workflow.md) : clé du ticket Jira à la fin du sujet des commits, clé de l'epic du jalon à la fin du titre des PR, aucune clé dans le nom des branches, commits et PR au seul nom de Julien (2026-09-30)

### Decided

- Jeu de données : Pokémon, CSV PokéAPI en français ([ADR-0001](adr/0001-mvp-jeu-de-donnees-pokeapi.md))
- Environnement cible : Google Cloud, dbt hors POC ([ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md))
- Chargement des données en Cypher pur ([ADR-0003](adr/0003-mvp-chargement-cypher-pur.md))
- Modèle du graphe : espèce + toutes les formes ([ADR-0004](adr/0004-mvp-modele-espece-formes.md))
- Conventions de nommage du schéma : camelCase, `Pokemon`, relation vers la forme par défaut ([ADR-0005](adr/0005-mvp-conventions-nommage-schema.md))
- Banc d'essai : 30 questions de référence en 6 catégories ([ADR-0006](adr/0006-mvp-banc-essai-30-questions.md))
- Secrets dans Secret Manager, plus de `.env` ; services gérés, le poste local n'est qu'un client, plus de repli Docker ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md))

---

## Conventions

- **Added** : nouvelle feature
- **Changed** : modification d'une feature existante
- **Deprecated** : feature qui va disparaître
- **Removed** : feature supprimée
- **Fixed** : bug fix
- **Security** : correctif de sécurité
- **Decided** : décision tech structurante (lien vers ADR)

Bugs fixés et features livrées vont **dans le même fichier** (pas de bugs log séparé).
