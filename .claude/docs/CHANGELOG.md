# Changelog — node4jPOC

Format : [Keep a Changelog](https://keepachangelog.com/). Versionning : `vYYYY.MM.DD-HHMM` (tag de déploiement).

## [Unreleased]

### Added

- {{Nouvelle feature 1}}

### Changed

- Pivot 2026-09-28 : environnement cible Google Cloud, découpage en 6 jalons ([CR](cadrage/reunions/2026-09-28-pivot.md))

### Fixed

- {{Bug fixé}}

### Decided

- Jeu de données : Pokémon, CSV PokéAPI en français ([ADR-0001](adr/0001-mvp-jeu-de-donnees-pokeapi.md))
- Environnement cible : Google Cloud, dbt hors POC ([ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md))
- Chargement des données en Cypher pur ([ADR-0003](adr/0003-mvp-chargement-cypher-pur.md))
- Modèle du graphe : espèce + toutes les formes ([ADR-0004](adr/0004-mvp-modele-espece-formes.md))

## [v{{YYYY.MM.DD-HHMM}}] — {{YYYY-MM-DD}}

### Added

- {{Initialisation projet}}

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
