# HANDOFF — 2026-10-20 08h30

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/003-phase-15-campagnes` (PR n°44, avec ce handoff ; fusion juste après, feu vert de Julien)
**Spec en cours** : [003-graphrag-descriptions](specs/003-graphrag-descriptions/spec.md) (27/35 tasks)
**Goal session** : le gel (T14.2), puis `g-1` (T15.2), `t2-controle` (T15.3) et la mesure de T17.1, avec la clé actuelle

## Status

- ✅ T14.2 (PR n°43, fusionnée ; NEO-33 publié, critère 1 coché) : `gel = 2026-10-19T23:24:40`, `pilote = "pilote-3"`, commit `27614ab` au plan (D12) ; seuils rappelés ; plafond de `g-1` 8,64 $
- ✅ T15.2 et T15.3 (PR n°44) : `g-1` le 2026-10-20 de 0 h 18 à 1 h 17, 180 réponses sans panne, 5,061 $ ; `t2-controle` juste après, 1,617 $ (`adk-gemini` : 9 échecs « tours ») ; traces conformes ; scores masqués jusqu'à la revue
- ⏳ T17.1 : `banc recherche-seule --campagne g-1` conforme (gel `27614abd1aad`) ; pré-classement des 55 espèces hors filet (Wailord acceptable pour Q9, 54 écartées dont 3 cas limites) dans `logs/recherche-seule/g-1-pre-classement.md` (hors git), en attente de Julien
- Dépense : Console avant `g-1`, 30,63 $ de crédits et 7,43 $ sur 20 $ en octobre ; après, ≈ 10,99 $ calculés ; spec ≈ 8,47 $ sous 10 $

## Échecs tentés (à ne pas refaire)

- D'autres commandes pendant la suite complète : `test_serveur_perdu_en_fin_de_tour` échoue sous la charge (gotcha) → la suite seule ; rien de modifié sous `banc/` pendant une campagne
- Attendus de test tirés des constantes du module → valeurs de la spec en clair (leçon du 2026-10-17)

## Blocked on

- L'accord de Julien sur le pré-classement de T17.1 ; T2.2 attend sa nouvelle clé (avant le 2026-11-07)

## Next (par ordre)

1. **NEO-33** : « Résultats du 2026-10-20 (T15.2, T15.3) », PR n°44 en lien, montré puis publié (critère 2 : séries notées après la revue)
2. **T17.1** : accord (cas limites : Mégapagos Q9, Roucarnage Q16, Monaflèmit Q26) ; précision D13, case cochée, PR de la phase 17 (NEO-35) ; NEO-35 montré puis publié
3. **T16.1** : revue assistée de `g-1` puis `t2-controle` (`banc contre-epreuve` : 8 cas par campagne que Julien revoit seul, pré-analyse scellée)
4. **T16.3** : Console (jour UTC du 2026-10-19 : pilote 0,943 $, `g-1` 2,797 $, `t2-controle` 0,766 $ pour Claude) et export (22 h et 23 h UTC, où `g-1` et `t2-controle` se mêlent) ; **T2.2** avant le 2026-11-07

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 003-graphrag-descriptions
Task: T17.1
Fichiers en cours: logs/recherche-seule/g-1-pre-classement.md
Bloqué sur: accord de Julien sur le pré-classement
Commande de reprise: git switch main && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
