# HANDOFF — 2026-10-19 22h30

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/003-phase-14-pilote` (PR n°42 ; fusion après ce handoff, feu vert de Julien)
**Spec en cours** : [003-graphrag-descriptions](specs/003-graphrag-descriptions/spec.md) (24/35 tasks)
**Goal session** : sans la clé de T2.2, T16.3 en partie et T17.1 ; puis le pilote T14.1, avec la clé actuelle (choix de Julien)

## Status

- ✅ T16.3 en partie (PR n°40) et T17.1 en partie (PR n°41), fusionnées ; sections publiées dans NEO-33 et NEO-35
- ✅ T14.1 (PR n°42) : `pilote-3` complet, 60 réponses, 1,697 $, clé actuelle (plan, D15) ; traces conformes ; 21 décisions de Claude validées par Julien ; scores non comptés 13,5 et 18,5 sur 30 ; Akwakwak acceptable pour Q17, hors filet ; aucun réglage (plan, D12, D14)
- ⏳ NEO-33 : « Résultats du 2026-10-19 (T14.1) » montrés à Julien, publiés après la fusion

## Échecs tentés (à ne pas refaire)

- Attendus de test tirés des constantes du module : un réglage faux passe inaperçu → valeurs de la spec en clair
- Deux mutations de même taille dans la même seconde partageaient un `.pyc` → outil corrigé (gotcha) ; ni commit ni édition pendant un lancement
- D'autres commandes pendant la suite complète : `test_serveur_perdu_en_fin_de_tour` échoue sous la charge (gotcha) → la suite seule
- `banc contre-epreuve --enregistrer` pour un pilote : sa note de tête parle d'une contre-épreuve → corrigée à la main (gotcha)

## Blocked on

- Rien : T14.2 (gel) d'abord, à tête reposée (choix de Julien) ; T2.2 avant le 2026-11-07, avec la nouvelle clé de Julien

## Next (par ordre)

1. **T14.2** (NEO-33) : gel du jalon 3, table `[[jalon]]` en tête de `revues.toml` (`gel = AAAA-MM-JJTHH:MM:SS`, `pilote = "pilote-3"`), commit noté au plan ; seuils de D12 rappelés ; plafond de `g-1` ≈ 8,64 $ (1,5 × 5,1 + 1) ; relu par Julien. Aucune revue avant : les décisions de `pilote-3` ne sont protégées qu'une fois déclarées
2. **T15.2 et T15.3** : `g-1` (3 passes, ≈ 5,1 $) et `t2-controle` (≈ 1,6 $), feu vert de Julien ; puis `banc controle-traces`, `scripts/traces.sh` et la mesure de T17.1 (`banc recherche-seule --campagne g-1`)
3. **T2.2** avant le 2026-11-07 (avant `g-1` si la campagne risque de déborder) : nouvelle clé de Julien, déposée par le presse-papier (pipe, sans affichage) ; `banc.sh acces` (~0,003 $) ; sa PR (NEO-29)

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 003-graphrag-descriptions
Task: T14.2
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch main && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
