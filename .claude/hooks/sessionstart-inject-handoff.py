#!/usr/bin/env python3
"""
SessionStart hook — flux selon la source :

1. source="compact" (matcher compact) — comportement historique :
   re-inject le snapshot pré-compaction pointé par le marker
   /tmp/claude-handoff-marker-<session_id>.json (écrit par precompact-snapshot-handoff.py),
   et ré-arme l'injection des gotchas ciblés (le contexte vient d'être résumé).

2. source="startup" (matcher startup) — filet « n'oublie rien » + filet budget (v1.4.1) :
   si .claude/.cache/session-end-snapshot.md (écrit par sessionend-snapshot.py, UNIQUEMENT
   quand une session s'est fermée sans /handoff en laissant une trace git — v1.5.0) est
   PLUS FRAIS que .claude/docs/HANDOFF.md → l'injecter. Dans TOUS les cas, le consommer
   (unlink) pour ne jamais réinjecter un filet périmé.

   Toujours au startup : agent teams actives (flag) sans le plugin agent-teams → rappel (flux 4).

3. source="startup" | "resume" | "clear" | "fork" — marqueur de début de session (horodatage +
   empreinte git + signature de HANDOFF.md) relu par sessionend-snapshot.py ; au startup, purge
   du cache par-session de plus de 7 jours.

Payload sans champ "source" (schéma historique) → flux marker (1).
Stdout = injecté automatiquement dans le contexte par Claude Code (documenté).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from snapshot_common import mark_session_start, purge_stale_cache


def racine_projet(data) -> str:
    """Racine du projet : CLAUDE_PROJECT_DIR (fixe pour la session), sinon le cwd du payload.

    Le cwd du payload suit les `cd` : une session restée dans un sous-dossier ne trouvait plus
    ni le filet ni le HANDOFF (même règle que posttooluse-growth-detection depuis la PR n°2).
    """
    return os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()


def inject_compact_marker(data) -> None:
    """Flux 1 : ré-injection post-compaction via marker par-session."""
    session_id = data.get("session_id", "unknown")

    marker_path = Path(tempfile.gettempdir()) / f"claude-handoff-marker-{session_id}.json"
    if not marker_path.exists():
        # Pas de marker → pas de re-injection nécessaire (session normale)
        return

    try:
        marker = json.loads(marker_path.read_text())
    except Exception:
        return

    if not marker.get("needs_inject"):
        return

    snapshot_path = Path(marker.get("snapshot_path", ""))
    if not snapshot_path.exists():
        return

    try:
        snapshot = snapshot_path.read_text(encoding="utf-8")
    except Exception:
        return
    if not snapshot:
        return

    # Stdout direct = injection auto par Claude Code dans le contexte
    print(
        f"""## 🔄 Re-injection post-compaction

Le contexte vient d'être compacté. Voici le snapshot HANDOFF.md récent pour reprendre où on en était :

{snapshot[:5000]}

→ Lis aussi `.claude/docs/HANDOFF.md` pour l'historique complet si besoin.
→ Continue ton travail. Si tu finis ta session, lance `/handoff` pour propre snapshot."""
    )

    # Consommé : un marqueur par session compactée s'accumulait dans $TMPDIR (jamais purgé)
    try:
        marker_path.unlink()
    except OSError:
        pass


def inject_session_end_net(data) -> None:
    """Flux 2 : filet fin de session — injecte si plus frais que HANDOFF.md, puis consomme."""
    cwd = racine_projet(data)
    snap = Path(cwd) / ".claude" / ".cache" / "session-end-snapshot.md"
    if not snap.exists():
        return

    handoff = Path(cwd) / ".claude" / "docs" / "HANDOFF.md"
    try:
        snap_mtime = snap.stat().st_mtime
        handoff_mtime = handoff.stat().st_mtime if handoff.exists() else 0.0
        if snap_mtime > handoff_mtime:
            content = snap.read_text(encoding="utf-8")[:5000]
            print(
                f"""## ⚠️ Filet mémoire — la session précédente a laissé du travail non consigné dans HANDOFF.md

Fermée sans /handoff (ou avec du travail après le dernier /handoff) — snapshot automatique de fin de session :

{content}

→ Croise avec `.claude/docs/HANDOFF.md` (possiblement stale) et propose à l'utilisateur de consolider via `/handoff`."""
            )
    except Exception:
        pass
    finally:
        # Consommé dans tous les cas : un filet ne se réinjecte jamais deux fois,
        # et si HANDOFF est plus frais c'est que /handoff a déjà capturé l'état.
        try:
            snap.unlink()
        except OSError:
            pass


def rearm_codemap_injection(data) -> None:
    """Post-compaction : efface le marker « gotchas déjà injectés » du hook PreToolUse
    (une injection par (session, fichier)) → la prochaine édition de chaque fichier ré-injecte
    ses gotchas, là où le rappel a de la valeur (le contexte vient d'être résumé)."""
    cwd = racine_projet(data)
    sid = re.sub(r"[^\w.-]", "_", str(data.get("session_id", "nosession")))
    try:
        (Path(cwd) / ".claude" / ".cache" / f"codemap-injected-{sid}.json").unlink()
    except OSError:
        pass


BUDGET_MAX_TOK = 25000  # override : CLAUDE_CONTEXT_BUDGET_MAX=<tok> (0 = désactivé)


def warn_context_budget(data) -> None:
    """Flux 3 (v1.4.1) — filet budget au démarrage : si la surface AUTO-CHARGÉE (CLAUDE.md +
    @-imports + rules non scopées) dépasse le seuil, le dire à Claude (stdout = contexte) avec
    les coupables et le remède. Claude Code affiche bien une notice native « Large <fichier>
    will impact performance (N chars > seuil) », mais rien n'en découle. Vécu 2026-09-16 sur un
    projet hors template : 13 imports, 780 Ko → plafond 1M dépassé à la reprise, session bloquée.
    Silencieux si context-budget.py est absent (profil script-jetable) ou si le seuil est à 0."""
    try:
        max_tok = int(os.environ.get("CLAUDE_CONTEXT_BUDGET_MAX", BUDGET_MAX_TOK))
    except ValueError:
        max_tok = BUDGET_MAX_TOK
    if max_tok <= 0:
        return
    cwd = Path(racine_projet(data))
    script = cwd / ".claude" / "skills" / "doc-health" / "scripts" / "context-budget.py"
    if not script.is_file():
        return
    try:
        r = subprocess.run([sys.executable, str(script), "--root", str(cwd), "--json", "--no-user"],
                           capture_output=True, text=True, timeout=10)
        j = json.loads(r.stdout)
    except Exception:
        return
    total = int(j.get("total_tok", 0))
    if total <= max_tok:
        return
    top = sorted(j.get("files", []), key=lambda f: -f.get("tok", 0))[:3]
    lines = [f"- {f['tok']} tok  `{f['path']}`" + (f" → {f['remedy']}" if f.get("remedy") else "")
             for f in top]
    print(f"""## 📏 Budget de contexte dépassé — {total} tokens auto-chargés (seuil {max_tok})

Cette session démarre lourde : CLAUDE.md, ses `@-imports` et les rules non scopées pèsent ~{total} tokens
(estimation chars/2), rechargés à CHAQUE appel API. Coupables :
{chr(10).join(lines)}

→ Signale-le à l'utilisateur en 1 ligne et propose `/doc-health` (Étape 0) — projet < v1.4 : `slim-context.py`
du template. Ne modifie aucun fichier sans son accord.""")


TEAM_ENV = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"


def warn_team_without_plugin(data) -> None:
    """Flux 4 — agent teams actives SANS le plugin agent-teams : le dire, jamais en silence.
    Le flag monte une équipe à chaque session et fait partir tout subagent nommé en teammate
    (doc agent teams) ; sans le plugin, aucun invariant d'équipe n'est injecté et l'interrupteur
    `/agent-teams:team off` n'existe pas. Vécu : flag posé en user → toutes les sessions de tous
    les projets. Plugin activé = 1re clé `agent-teams@…` de `enabledPlugins` par priorité
    local > projet > user. Coupé par CLAUDE_TEAMS_PLUGIN_CHECK=off."""
    if os.environ.get("CLAUDE_TEAMS_PLUGIN_CHECK", "").lower() == "off":
        return
    if os.environ.get(TEAM_ENV, "").strip().lower() not in ("1", "true", "yes", "on"):
        return
    root = Path(racine_projet(data))
    user_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    plugin, src = None, None
    for label, p in (("local", root / ".claude" / "settings.local.json"),
                     ("projet", root / ".claude" / "settings.json"),
                     ("user", user_dir / "settings.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        ep = d.get("enabledPlugins")
        if plugin is None and isinstance(ep, dict):
            plugin = next((bool(v) for k, v in ep.items() if k.startswith("agent-teams@")), None)
        env = d.get("env")
        if src is None and isinstance(env, dict) and TEAM_ENV in env:
            src = f"{label} — `{p}`"
    if plugin:
        return
    print(f"""## ⚠️ Agent teams actives, plugin `agent-teams` absent

Le flag `{TEAM_ENV}` est à 1 (source : {src or "export shell"}) mais le plugin `agent-teams` n'est pas
activé ici : chaque session monte une équipe, et tout subagent nommé part en teammate SANS règles
d'équipe (rapport au lead, périmètre, docs partagés) ; `/agent-teams:team on|off|status` n'existe pas.

→ Signale-le à l'utilisateur en 1 ligne, sans rien modifier. Remèdes : installer le plugin
(`claude plugin install agent-teams@claude-setup --scope project`, puis `/agent-teams:team status`), ou
couper le flag (le retirer de sa source, ou `"{TEAM_ENV}": "0"` dans `env` de `.claude/settings.json`).
Pour faire taire ce rappel : `CLAUDE_TEAMS_PLUGIN_CHECK=off`.""")


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    source = data.get("source")
    cwd = racine_projet(data)
    if source in ("compact", None):  # post-compaction (ou schéma historique sans « source »)
        rearm_codemap_injection(data)
        inject_compact_marker(data)
    else:  # startup · resume · clear · fork (/fork, /branch, --fork-session) · futures sources
        if (Path(cwd) / ".claude").is_dir():
            if source == "startup":
                purge_stale_cache(cwd)
            mark_session_start(cwd, data.get("session_id"))
        if source == "startup":
            inject_session_end_net(data)
            warn_context_budget(data)
            warn_team_without_plugin(data)

    sys.exit(0)


if __name__ == "__main__":
    main()
