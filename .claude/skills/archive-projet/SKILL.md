---
name: archive-projet
description: Archive un projet en fin de vie (ou le restaure) — bilan final (HANDOFF/ROADMAP/CHANGELOG), marquage archivé lisible par toute session future (bannière CLAUDE.md + marqueur .claude/archived), scan des références de chemin (repo, crontab, ~/.claude.json), migration de l'auto-memory, puis commande de move vers _archives/ remise à l'utilisateur (à lancer après fermeture de session). Modes restore (dé-archiver) et status.
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion, Bash(python3 .claude/skills/archive-projet/scripts/archive-projet.py:*), Bash(git status), Bash(git log:*), Bash(git worktree list:*), Bash(git add:*), Bash(git commit:*), Bash(date:*), Bash(crontab -l)
disable-model-invocation: true
argument-hint: "[\"raison\"|restore|status] [--dest <dossier>]"
---

# /archive-projet — Fin de vie d'un projet (archiver / restaurer)

> **Quand ne PAS utiliser** : livraison d'une feature (le projet continue) → `/feature-done` ·
> fin de session simple → `/handoff` · changement de direction (le projet continue) → `/pivot` ·
> archiver des leçons anciennes → `/lecon archive` · archiver des idées → `/idee archive`.
> **Réversibilité** : 🟠 marquage + move réversibles via le mode `restore` (l'auto-memory est
> migrée dans les deux sens) — mais les approbations et l'historique `/resume`, keyés par chemin
> dans `~/.claude.json`, repartent de zéro après un move (bénin : re-prompt une fois), et le
> `mv` final est un geste manuel post-session.

Ton rôle : clôturer proprement un projet (ou le rouvrir) **sans angle mort** — état final
capturé, marquage visible par toute session future, mémoire migrée, référents externes
rapportés. Le script bundlé fait la partie déterministe (marqueur, bannière, scan, slug
mémoire, commande finale) ; toi tu fais le bilan documentaire, le commit et l'interprétation
du rapport.

## Modes

| Mode                                            | Quand l'invoquer                                 |
| ----------------------------------------------- | ------------------------------------------------ |
| `/archive-projet ["raison"] [--dest <dir>]`     | Projet terminé/abandonné/en pause longue → archiver |
| `/archive-projet restore`                       | Reprendre un projet archivé                      |
| `/archive-projet status`                        | Voir l'état d'archivage                          |

La destination est **choisie par l'utilisateur au moment de l'archivage** (Étape 2) — elle
n'est pas forcément la même d'un projet à l'autre. Défaut proposé : `<parent>/_archives/<projet>`
(ex. `~/projets/hub/X` → `~/projets/hub/_archives/X`) ; tout autre dossier via `--dest`.

---

## MODE archiver (défaut)

### Étape 1 — Bilan de fermeture (AVANT toute mécanique)

1. Demander la **raison** (livré / abandonné / pause longue) si non fournie — elle va dans le
   marqueur et la bannière.
2. HANDOFF final (même logique que `/handoff`) : status réel, échecs tentés, Continuation
   State — c'est ce qui permettra une reprise dans 6 mois.
3. ROADMAP : geler l'état **réel** (statuer chaque ligne — pas d'embellissement).
4. CHANGELOG : entrée `## YYYY-MM-DD — Archivage (<raison>)`.
5. Proposer (sans forcer) une leçon post-mortem → `/lecon`.

### Étape 2 — Choix de la destination (AskUserQuestion — TOUJOURS demander)

Ne jamais imposer la destination : la proposer via AskUserQuestion avec :

- `<parent>/_archives/<projet>` — défaut (Recommended) ;
- si un ou des dossiers d'archives existent déjà ailleurs (visibles en listant le parent ou
  déjà utilisés dans `~/projets/`), les proposer aussi ;
- tout autre chemin via « Other » (champ libre).

Le choix devient `--dest <dir>` pour toutes les commandes qui suivent (omis si défaut).

### Étape 3 — Dry-run du script + gate utilisateur

```bash
python3 .claude/skills/archive-projet/scripts/archive-projet.py archive \
  --reason "<raison>" [--dest <dir>] --dry-run
```

Montrer le résultat : destination, références internes au chemin absolu, référents externes
détectés (crontab, `~/.claude.json`), auto-memory trouvée ou non. **Attendre le OK.**

### Étape 4 — Exécution réelle (sans `--dry-run`)

Le script écrit `.claude/archived` (date, raison, chemins aller/retour) et insère la bannière
en tête du `CLAUDE.md` racine (entre marqueurs HTML) — c'est **elle** qui fait que toute
session future SAIT que le projet est archivé (CLAUDE.md est auto-chargé). Il **refuse** si
des worktrees sont actifs (les merger/retirer d'abord) ou si le projet est déjà archivé.

### Étape 5 — Rapport des référents externes

Pour chaque occurrence du chemin hors repo : dire à l'utilisateur ce qui **cassera** après le
move et où repointer — crontab, CI, et si projet n8n : vérifier via les outils n8n-mcp qu'aucun
workflow n'appelle un script local du projet. Le script ne corrige PAS ces référents (il ne
peut pas deviner la cible) — toi tu les listes, l'utilisateur tranche.

### Étape 6 — Commit final (si repo git)

```bash
git status --short     # relire : seuls CLAUDE.md, .claude/ (docs + marqueur) doivent bouger
git add CLAUDE.md .claude/ && git commit -m "chore(archive): projet archivé — <raison>"
```

### Étape 7 — Remettre la commande finale

Copier-coller à l'utilisateur la commande imprimée par le script (`mkdir -p` destination +
`mv` du projet + `mv` du dossier auto-memory vers le nouveau slug), avec la consigne :
**fermer cette session D'ABORD, puis lancer la commande depuis un autre terminal.**
Ne JAMAIS l'exécuter toi-même depuis cette session — elle tourne dans le dossier à déplacer
(cwd, hooks et approbations sont keyés sur ce chemin).

---

## MODE restore

1. `python3 .claude/skills/archive-projet/scripts/archive-projet.py restore --dry-run`
   → montrer chemin de retour (lu dans le marqueur, override `--dest`) + état auto-memory. Gate.
2. Exécution réelle : le script retire la bannière et le marqueur.
3. CHANGELOG : entrée `## YYYY-MM-DD — Dé-archivage (reprise)`. Commit.
4. Remettre la commande finale de move retour (même consigne : fermer la session d'abord).
5. Conseiller : à la première session post-retour, reprendre par le HANDOFF (« Commande de
   reprise » du Continuation State).

## MODE status

```bash
python3 .claude/skills/archive-projet/scripts/archive-projet.py status
```

Affiche le marqueur (date, raison, chemins) ou « non archivé ».

---

## Anti-patterns

- ❌ Exécuter le `mv` final depuis la session courante (elle tourne DANS le dossier déplacé)
- ❌ Archiver avec des worktrees actifs (le script bloque — merger/retirer d'abord)
- ❌ Embellir la ROADMAP au bilan (l'état final doit être l'état RÉEL, échecs compris)
- ❌ Éditer `~/.claude.json` pour « migrer » les approbations (config vivante — on n'y touche pas)
- ❌ Archiver pour ranger un projet actif (pause courte = `/handoff` suffit)
- ❌ Imposer la destination sans la demander (Étape 2 — le choix appartient à l'utilisateur)
- ❌ Oublier le commit de l'Étape 5 (bannière + marqueur non versionnés = sessions futures aveugles)
