# `.claude/agents/` — Organisation

> Custom agents (sous-agents Claude spécialisés), **à plat** dans ce dossier.

## Convention

```
.claude/agents/
├── <agent-1>.md
├── <agent-2>.md
└── ...
```

**Pas de sous-dossier de regroupement.** Claude Code scanne `.claude/agents/<nom>.md` à **1 niveau** (même limitation que skills, cf. [issue #18192](https://github.com/anthropics/claude-code/issues/18192)).

## Règles

1. **L'identifier vient du frontmatter `name:`** (qui doit matcher le nom du fichier).
   Ex : `.claude/agents/doc-maintainer.md` avec `name: doc-maintainer` → invoquable via Task tool avec `subagent_type: doc-maintainer`.

2. **Frontmatter requis** : `name`, `description`, `tools`, `model: inherit` (ou model ID).

3. **Tout est dans le même espace de noms** — pas de collision possible avec namespacing par sous-dossier.

4. **Rôle teammate → `SendMessage` OBLIGATOIRE dans `tools:`** (tout agent, sauf subagent pur type `doc-maintainer`). Spawné **nommé**, un agent tourne en teammate et ne peut rapporter au lead QUE via `SendMessage` — sans lui : rapport perdu, idle muet, zombie qui ping. **Vérifié en CI** (étape « Défs teammate — SendMessage »), donc pas besoin d'y penser : l'oubli fait échouer le build. Détail : rule d'équipe `agent-teams.md` (posée dans `.claude/rules/` par l'activation du plugin `agent-teams`).

## Invocation — subagent OU teammate

Un même fichier `.claude/agents/*.md` s'invoque de **deux façons** (jamais en slash `/agent-name`) :

1. **Subagent (Task tool)** — headless, invisible, one-shot ; le résultat revient comme
   retour d'outil. Ex : `Lance l'agent doc-maintainer pour un audit complet`.
2. **Teammate (agent teams — opt-in, plugin `agent-teams`)** — session Claude Code complète,
   spawnée par le lead à partir de la définition d'agent (tools + model honorés). Affichage
   `teammateMode: "auto"` (posé par l'activation) : un pane tmux par teammate si la session tourne
   dans tmux — le body **remplace** alors le system prompt par défaut —, sinon in-process dans le
   terminal courant — le body s'y **ajoute**. En général via `/agent-teams:team`.

Quand choisir quoi + protocole d'équipe (périmètre, cycle de vie, topologie) : rule
`.claude/rules/agent-teams.md` (posée par l'activation) + `skills/team/protocole.md` du plugin.

## Importer un agent externe

```bash
# Copier directement le .md dans .claude/agents/
cp <source>/agent.md .claude/agents/<agent-name>.md
# Si tu veux marquer la provenance → préfixer le nom : n8n-expert.md, etc.
```

## Limitations agents importés depuis plugins

Plugin agents ne supportent PAS les frontmatter fields : `hooks`, `mcpServers`, `permissionMode` (ignorés silencieusement). Pour ces fields → copier le `.md` localement dans `.claude/agents/`.

## Agents du template

| Agent             | Quoi                                                                           | Mode typique                         |
| ----------------- | ------------------------------------------------------------------------------ | ------------------------------------ |
| `doc-maintainer`  | Maintenance doc EN LOT (livraisons, audit + actions, promotions) — jamais le HANDOFF. Diff par diff. | Subagent (Task)                      |
| `reviewer`        | Review **lecture seule** — diffs ET plans (`/conception`), findings 🔴/🟠/🟢   | Subagent ou teammate                 |
| `explore-code`    | Explorateur code (lecture seule) — patterns/intégration en `chemin:ligne`      | Subagent ou teammate (`/conception`) |
| `explore-docs`    | Explorateur docs externes — context7 → MCP → web, URLs + versions              | Subagent ou teammate (`/conception`) |
| `explore-memoire` | Explorateur mémoire projet — ADRs/leçons/idées : « déjà décidé/tenté ? »       | Subagent ou teammate (`/conception`) |

Les rôles portent chacun UNIQUEMENT leur spécialité ; le protocole d'équipe
(communication, périmètre, cycle de vie, topologie) vit dans la rule `agent-teams.md` (invariants,
posée par l'activation du plugin `agent-teams`) et, en version longue, dans `skills/team/protocole.md`
du plugin — pas de duplication ici.

> 🧩 Les **rôles d'exécution** (`worker` · `front-end` · `back-end` · `tester`) +
> `/agent-teams:team` + le hook de trace vivent dans le **plugin `agent-teams`**
> (`/plugin install agent-teams@claude-setup`) — auto-découverts à l'installation.
