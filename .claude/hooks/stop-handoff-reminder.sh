#!/usr/bin/env bash
# Stop hook — Rappel /handoff si HANDOFF.md est stale (> 1 jour) ou trop gros.
#
# Trigger : à chaque fin de tour Claude (event Stop).
# Action (UNE fois par session et par motif — v1.5.0 : avant, le rappel d'âge repartait
# à CHAQUE tour tant que la condition tenait) :
#   - HANDOFF.md > 12 000 octets → rappel taille (il est auto-chargé à chaque session)
#   - HANDOFF.md > 24h ET changements git → suggérer /handoff
#
# Non-blocking (juste systemMessage, visible par l'utilisateur).
#
# ── MULTI-AGENT / lead-only (à lire) ────────────────────────────────────────
# Le but est qu'UN SEUL rappel parte (celui du lead), pas N (un par teammate)
# sur le même HANDOFF.md partagé. Ce qui est vrai d'après la doc des hooks :
#   • Les sous-agents déclenchent SubagentStop (non câblé) → zéro spam de leur côté.
#   • Stop ne porte PAS de champ "agent_type" (réservé à SubagentStop). Les teammates
#     d'une agent team sont des sessions Claude Code à part entière : indiscernables
#     du lead depuis la payload.
# Leviers fournis :
#   • Gate défensif sur agent_type SI jamais présent (compat future / SubagentStop).
#   • Variable d'env CLAUDE_HANDOFF_REMINDER=0|off|false|no → coupe le rappel
#     (à exporter dans le lanceur des sessions teammate pour le cas top-level).
#   • Marqueurs une-fois-par-session (.claude/.cache/handoff-{size,age}-warned-<sid>).
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Levier explicite de désactivation (cas teammates = sessions indépendantes).
case "${CLAUDE_HANDOFF_REMINDER:-}" in
  0 | off | false | no | OFF | FALSE | NO) exit 0 ;;
esac

# Lire stdin JSON (Claude Code hook event)
INPUT=$(cat)

# Parsing PORTABLE via python3 (pas de grep -oP, GNU-only / absent sur macOS).
# Extrait cwd, agent_type et session_id (assaini), séparés par des tabulations.
PARSED=$(printf '%s' "$INPUT" | python3 -c '
import json, re, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
cwd = d.get("cwd") or ""
agent = d.get("agent_type") or d.get("agentType") or ""
sid = re.sub(r"[^\w.-]", "_", str(d.get("session_id") or "nosession"))
sys.stdout.write(cwd + "\t" + agent + "\t" + sid)
' 2>/dev/null || printf '\t\tnosession')

CWD="${PARSED%%$'\t'*}"
REST="${PARSED#*$'\t'}"
AGENT="${REST%%$'\t'*}"
SID="${REST#*$'\t'}"
if [ -z "$CWD" ]; then CWD="$PWD"; fi
if [ -z "$SID" ]; then SID="nosession"; fi

# Gate lead-only défensif : si agent_type est présent ET n'est pas le lead,
# c'est un teammate/sous-agent → on sort sans rappeler. (Stop n'expose
# normalement pas ce champ ; absent ⇒ on suppose le lead et on continue.)
case "$AGENT" in
  "" | lead | main) : ;; # lead présumé → continuer
  *) exit 0 ;;           # teammate / sous-agent identifié → pas de rappel
esac

# Projet archivé (/archive-projet) → lecture seule, pas de rappel /handoff
if [ -f "$CWD/.claude/archived" ]; then
  exit 0
fi

HANDOFF="$CWD/.claude/docs/HANDOFF.md"

if [ ! -f "$HANDOFF" ]; then
  exit 0
fi

CACHE="$CWD/.claude/.cache"

# Pose le marqueur une-fois-par-session ; code retour 1 si déjà posé (rappel déjà fait).
first_time() {
  local mark="$CACHE/$1-$SID"
  [ -f "$mark" ] && return 1
  mkdir -p "$CACHE" 2>/dev/null && : > "$mark"
  return 0
}

# Garde-fou TAILLE (v1.4.1) — HANDOFF est auto-chargé à CHAQUE session (@-import), cible ≤ 40 lignes.
# Vécu 2026-09-16 (projet hors template) : 55 sections datées empilées → 175 Ko rechargés à chaque
# appel, plafond 1M dépassé à la reprise. Seuil 12 000 octets (~6k tokens) ; une fois par session.
MAX_BYTES="${CLAUDE_HANDOFF_MAX_BYTES:-12000}"
SIZE=$(stat -c %s "$HANDOFF" 2>/dev/null || stat -f %z "$HANDOFF" 2>/dev/null || echo 0)
if [ "$MAX_BYTES" -gt 0 ] && [ "$SIZE" -gt "$MAX_BYTES" ]; then
  if first_time handoff-size-warned; then
    LINES=$(wc -l < "$HANDOFF" 2>/dev/null | tr -d ' ')
    echo "{\"systemMessage\": \"📏 HANDOFF.md fait $((SIZE / 1024)) Ko / ${LINES} lignes — auto-chargé à chaque session (cible ≤ 40 lignes). /handoff le condense : l'historique part dans HANDOFF-journal.md.\"}"
    exit 0
  fi
fi

# Âge en secondes
NOW=$(date +%s)
MTIME=$(stat -c %Y "$HANDOFF" 2>/dev/null || stat -f %m "$HANDOFF" 2>/dev/null || echo "$NOW")
AGE_SEC=$((NOW - MTIME))
AGE_HOURS=$((AGE_SEC / 3600))

# Seuil : 24h
if [ "$AGE_HOURS" -lt 24 ]; then
  exit 0
fi

# Vérifier qu'il y a des changements git (sinon rappel inutile)
cd "$CWD" 2>/dev/null || exit 0
if [ -z "$(git status --short 2>/dev/null)" ]; then
  exit 0  # rien changé, pas la peine de rappeler
fi

# Une fois par session : le rappel ne doit pas suivre chaque réponse de Claude.
first_time handoff-age-warned || exit 0

# Non-blocking notification
echo "{\"systemMessage\": \"⏰ HANDOFF.md date de ${AGE_HOURS}h. Pense à /handoff avant la fin de session.\"}"
exit 0
