# Idée — Mises à jour des données PokéAPI, automatiques et surveillées

**Date :** 2026-09-30
**Source :** Julien, en session, après « ces CSV se mettent à jour tout seuls ? » : « à quoi ça sert si les données ne peuvent pas évoluer ».

## Pitch

Faire suivre au graphe les évolutions de PokéAPI (nouveaux Pokémon, corrections) sans perdre la reproductibilité : passer à un commit plus récent, recalculer les valeurs attendues, recharger, rejouer les 30 questions. Si possible automatiquement tous les X jours, avec une alerte quand une étape échoue : l'alerting est à mettre en place aussi.

## Use case

PokéAPI corrige des évolutions : 8 commits ont touché les CSV du 8 au 26 septembre 2026. Tous les X jours, une tâche planifiée repère un nouveau commit sur `data/v2/csv`, recalcule les valeurs attendues, recharge Aura et rejoue les questions. Tout passe : la référence avance d'un commit. Une étape échoue : une alerte part, et la référence reste sur le commit précédent.

## Effort estimé

Gros (> 1 sem), estimation de Claude à confirmer : détection des nouveaux commits, recalcul indépendant, planification sur Google Cloud et alerting.

## Pistes et questions ouvertes

- Reproductibilité ([ADR-0001](../adr/0001-mvp-jeu-de-donnees-pokeapi.md)) : chaque mesure reste attachée à un commit. On met à jour entre deux campagnes de mesure, jamais pendant, et le tableau comparatif note le commit utilisé.
- Recalculer les valeurs attendues en lisant les CSV directement, pas le graphe : sinon la vérification se valide elle-même.
- Une réponse de référence peut changer pour une bonne raison (nouveau Pokémon) : distinguer une évolution d'une régression (rapport des écarts, validation humaine ?).
- Où tourner : un service géré ([ADR-0007](../adr/0007-infra-secrets-et-services-geres.md)), par exemple Cloud Scheduler et un job Cloud Run, pas le poste local.
- Alerting : canal à choisir (Cloud Monitoring, e-mail…), comme la fréquence X.
- Effet de bord : une activité régulière évite la pause de l'instance Free après 72 h.

## Statut

💡 **Backlog**
