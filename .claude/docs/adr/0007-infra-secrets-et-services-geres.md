---
status: accepted
scope: infra
phase: 2026-Q3
supersedes: null
---

# 0007 — Secrets dans Secret Manager, services gérés : le poste local n'est qu'un client

**Statut :** Accepted
**Date :** 2026-09-30
**Décideur :** Julien Leroy

## Contexte

Le brief et le plan de la spec 001 mettaient les identifiants d'Aura dans un `.env` à la racine, gitignoré et illisible par Claude, avec un repli sur Neo4j en local avec Docker. Le 2026-09-30, Julien fixe une autre règle : « on mettra toutes les clés dans Secret Manager ». La skill Jira marche déjà ainsi : sa clé est lue dans Secret Manager au moment de servir et n'existe jamais sur le disque. La règle vaut pour tout le POC, dont chaque technique aura ses clés (Aura, Google Cloud, LLM).

## Options considérées

- **Option A — `.env` à la racine (le plan, ne rien faire)** : simple, `cypher-shell` lit ses variables tout seul. Mais un fichier de secrets reste sur le disque, gardé par `.gitignore` et une règle de lecture, à recopier sur chaque poste ; rien de transposable.
- **Option B — Secret Manager, lu au moment de servir** : rien sur le disque ; droits IAM et journal d'audit de Google Cloud ; le modèle d'une entreprise full Google Cloud ([ADR-0002](0002-cadrage-environnement-cible-google-cloud.md)).
- **Option C — gestionnaire de mots de passe en ligne de commande** (1Password, Bitwarden) : rien sur le disque non plus, mais un outil de plus, hors de l'environnement visé.

## Décision

**Option B** (Julien). Les services du POC sont gérés : Neo4j Aura et Google Cloud. Le poste local n'est qu'un client : il porte les outils (`gcloud`, `cypher-shell`, scripts, Claude Code), ni secret, ni base de référence, ni serveur.

- Un secret par service, dans le projet `jleroy-labo`, réplication `europe-west9` : liste et contenu dans [ACCESS.md](../ACCESS.md).
- Un script lit son secret au lancement (`gcloud secrets versions access`) et le passe à l'outil par l'environnement du processus, sans l'afficher ni l'écrire.
- Plus de `.env` ni de `.env.example`. Un fichier d'identifiants téléchargé (`Neo4j-*.txt`) reste ignoré par git et interdit en lecture : il ne fait que transiter, puis il est supprimé.
- Plus de repli local : si AuraDB Free ne suffit plus, on passe à une offre Aura payante ; le CDC du jalon 6, s'il est décidé, se testera sur une instance Business Critical louée à l'heure.

## Conséquences

- ✅ Aucun secret sur le disque ni dans le dépôt ; changer un mot de passe, c'est ajouter une version.
- ✅ Gratuit à cette échelle : 6 versions actives et 10 000 accès par mois offerts ; 2 versions actives aujourd'hui.
- ✅ Un principe sans exception : la base de référence et les secrets ne vivent que dans des services gérés.
- ⚠️ Pas de chargement sans réseau, ni sans `gcloud` connecté au compte fr.julienleroy.
- ⚠️ Une version désactivée reste facturée comme active : détruire les anciennes après une rotation.
- ⚠️ Le CDC du jalon 6 coûtera environ 0,40 $ par heure d'essai, au lieu de 0 $ en local.
- ⚠️ À adapter dans NEO-7 : T2.1, la spec 001 et son plan, ARCHITECTURE, le cadrage (§ Sécurité), le README (« Démarrer »), la stack et la ROADMAP (jalon 6).
- ⚠️ Transposition : en entreprise, l'accès au secret passe par un groupe ou un compte de service, pas par un compte personnel.

## Liens

- [ACCESS.md](../ACCESS.md) : secrets, instance Aura, réglages
- [ADR-0002](0002-cadrage-environnement-cible-google-cloud.md) : environnement cible Google Cloud
- [Spec 001, T2.1](../specs/001-socle-donnees/tasks.md)
- [Tarifs de Secret Manager](https://cloud.google.com/secret-manager/pricing), lus le 2026-09-30
