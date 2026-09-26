#!/usr/bin/env python3
"""upgrade.py — met à jour un projet généré depuis le template claude-Setup (merge 3 voies).

Principe — trois arbres par fichier de MÉTHODE :
  base  = ce qu'une init de la version du projet (vX) produirait (même profil, mêmes variables)
  cible = ce qu'une init de la nouvelle version (vY) produirait
  nous  = le projet actuel

  nous == cible          → déjà à jour
  nous == base           → le projet n'y a pas touché → la cible s'applique (maj / ajout / retrait)
  base == cible          → le template n'a pas bougé → le fichier du projet est gardé
  sinon (les deux ont bougé) → merge 3 voies (`git merge-file` ; fusion JSON pour settings.json).
                           Conflit → le fichier du projet est GARDÉ ; la version cible et le merge
                           annoté sont déposés dans .claude/.cache/upgrade-<vY>/ et signalés.

Jamais d'écrasement silencieux d'une modification locale. La doc projet (.claude/docs/) n'est
jamais fusionnée : seules des migrations versionnées et idempotentes y touchent (ex. < 1.4.0 :
journal HANDOFF et gotchas sortis des fichiers auto-chargés, via slim-context.py).

La base et la cible sont obtenues en REJOUANT l'init de chaque version (`git archive <tag>` →
render.py → cleanup-for-type.py de CETTE version) : le script tourne toujours depuis le template
le plus récent (logique d'upgrade à jour), mais chaque version est reconstruite par ses propres
scripts.

Usage :
  python3 <template>/.claude/skills/upgrade-template/scripts/upgrade.py --project <projet>
      [--template <dépôt local | URL git>] [--to vX.Y.Z | WORKTREE] [--from X.Y.Z]
      [--profile <type>] [--dry-run] [--json] [--allow-dirty]

  --template  défaut : "source" de .claude/template-lock.json, sinon le dépôt GitHub du template
  --to        défaut : dernier tag vX.Y.Z du template ; WORKTREE = l'arbre de travail tel quel (dev)
  --from      défaut : .claude/template-version du projet
  --profile   défaut : template-lock.json, sinon déduit (script-jetable / automation-n8n / web-app / python-app)

Code retour : 0 = à jour ou appliqué sans conflit · 1 = appliqué, conflits à résoudre · 2 = erreur
"""

import argparse
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import date
from pathlib import Path

DEFAULT_SOURCE = "https://github.com/kurt83340/claude-Setup"
# Dossiers du dépôt template qui ne vont jamais dans un projet (rsync documenté + strip de l'init)
EXCLUDE_TOP = {"EXAMPLES", "test", ".github", ".git", "plugins", ".claude-plugin"}
# Fichiers de MÉTHODE soumis à la mise à jour (la doc projet .claude/docs/ n'en fait jamais partie)
SCOPE_PREFIXES = (".claude/hooks/", ".claude/skills/", ".claude/agents/", ".claude/rules/")
SCOPE_FILES = (".claude/settings.json", ".claude/CLAUDE.md", ".claude/USAGE.md",
               ".claude/STRUCTURE.md", ".claude/template-version", "CLAUDE.md", ".gitignore",
               ".pre-commit-config.yaml", "workflows/README.md")
PROFILES = ("script-jetable", "automation-n8n", "python-app", "web-app", "bdd-migration", "other")
BOOTSTRAP_PREFIXES = (".claude/skills/init-from-template/", ".claude/skills/adopt-template/")
TEAM_RULE = ".claude/rules/agent-teams.md"
TEAM_RULE_SRC = "plugins/agent-teams/skills/team/agent-teams-rule.md"  # (v1.5.0+) dans le dépôt
TEAM_ENV = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"
CORE_RE = re.compile(r"\{\{([A-Z]{2,}_[A-Z][A-Z0-9_]+)\}\}")
MISSING = object()


class UpgradeError(Exception):
    pass


# ── Utilitaires ──────────────────────────────────────────────────────────────────────────────

def vtuple(v: str):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in nums[:3]) if nums else ()


def sh(args, cwd=None, check=True, data=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, input=data,
                       text=data is None or isinstance(data, str))
    if check and r.returncode != 0:
        err = r.stderr if isinstance(r.stderr, str) else r.stderr.decode("utf-8", "replace")
        raise UpgradeError(f"échec : {' '.join(map(str, args))}\n{err[-600:]}")
    return r


def read_bytes(p: Path):
    try:
        return p.read_bytes()
    except OSError:
        return None


def in_scope(rel: str) -> bool:
    if "__pycache__/" in rel or rel.endswith((".pyc", ".pyo")) or rel.endswith("/.DS_Store"):
        return False
    return rel in SCOPE_FILES or rel.startswith(SCOPE_PREFIXES)


def scoped_files(root: Path) -> set:
    out = set()
    for rel in SCOPE_FILES:
        if (root / rel).is_file():
            out.add(rel)
    for prefix in SCOPE_PREFIXES:
        d = root / prefix
        if d.is_dir():
            for f in d.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(root).as_posix()
                    if in_scope(rel):
                        out.add(rel)
    return out


# ── Arbres de version (base / cible) ─────────────────────────────────────────────────────────

def open_template(src: str, tmp: Path) -> Path:
    if re.match(r"^(https?://|git@|ssh://|file://)", src):
        dest = tmp / "template-repo"
        sh(["git", "clone", "--quiet", src, str(dest)])
        return dest
    p = Path(src).expanduser().resolve()
    if not p.is_dir():
        raise UpgradeError(f"template introuvable : {src}")
    return p


def is_git_repo(p: Path) -> bool:
    return sh(["git", "-C", str(p), "rev-parse", "--git-dir"], check=False).returncode == 0


def latest_tag(repo: Path):
    if not is_git_repo(repo):
        return None
    tags = sh(["git", "-C", str(repo), "tag", "--list", "v*"], check=False).stdout.split()
    tags = [t for t in tags if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
    return max(tags, key=vtuple) if tags else None


def extract(repo: Path, ref: str, dest: Path) -> bool:
    """Matérialise une version du template dans `dest` (sans les dossiers réservés au dépôt
    template). ref = tag/commit (git archive) ou WORKTREE (copie de l'arbre de travail)."""
    dest.mkdir(parents=True)
    if ref == "WORKTREE":
        for child in repo.iterdir():
            if child.name in EXCLUDE_TOP:
                continue
            target = dest / child.name
            if child.is_dir():
                shutil.copytree(child, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(child, target)
        return True
    r = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", ref], capture_output=True)
    if r.returncode != 0:
        return False
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
        members = [m for m in tar.getmembers()
                   if m.name.split("/")[0] not in EXCLUDE_TOP and ".." not in Path(m.name).parts
                   and not m.name.startswith("/") and (m.isfile() or m.isdir())]
        try:  # archive de NOTRE dépôt, déjà filtrée ; filtre « data » quand Python le connaît
            tar.extractall(dest, members=members, filter="data")
        except TypeError:
            tar.extractall(dest, members=members)  # noqa: S202
    return True


def replay_init(raw: Path, dest: Path, profile: str, brownfield: bool, vars_: dict, warnings: list):
    """Rejoue l'init de la version contenue dans `raw` (ses propres render.py + cleanup) → `dest`."""
    shutil.copytree(raw, dest)
    scripts = dest / ".claude" / "skills" / "init-from-template" / "scripts"
    if vars_ and (scripts / "render.py").is_file():
        vf = dest.parent / f"vars-{dest.name}.json"
        vf.write_text(json.dumps(vars_), encoding="utf-8")
        sh([sys.executable, str(scripts / "render.py"), "--vars", str(vf), "--root", str(dest)], check=False)
    cleanup = scripts / "cleanup-for-type.py"
    if not cleanup.is_file():
        warnings.append(f"{raw.name} : cleanup-for-type.py absent — arbre brut utilisé")
        return
    args = [sys.executable, str(cleanup), "--type", profile, "--root", str(dest)]
    if brownfield:
        args.append("--brownfield")
    r = sh(args, check=False)
    if r.returncode != 0:
        warnings.append(f"{raw.name} : profil « {profile} » inconnu de cette version → skills bootstrap "
                        "retirés à la main, sans purge de profil")
        for s in ("init-from-template", "adopt-template"):
            shutil.rmtree(dest / ".claude" / "skills" / s, ignore_errors=True)


# ── Déductions sur le projet ─────────────────────────────────────────────────────────────────

def infer_profile(project: Path) -> str:
    skills = project / ".claude" / "skills"
    if (skills / "handoff").is_dir() and not (skills / "spec").is_dir():
        return "script-jetable"
    if (project / "workflows").is_dir():
        return "automation-n8n"
    rules = project / ".claude" / "rules"
    if (rules / "code-style-web.md").is_file() and not (rules / "code-style.md").is_file():
        return "web-app"
    if (project / "package.json").is_file() and not any(
            (project / f).exists() for f in ("pyproject.toml", "requirements.txt", "setup.py")):
        return "web-app"
    return "python-app"


def infer_vars(raw_base: Path, project: Path) -> dict:
    """Retrouve les valeurs des placeholders CORE en alignant les fichiers bruts de la version de
    base (avec {{VAR}}) sur les fichiers rendus du projet (lignes appariées par difflib)."""
    found = {}
    # Ordre = priorité : .claude/CLAUDE.md d'abord (fichier de méthode, rarement retouché) ; le titre du
    # CLAUDE.md racine (souvent réécrit, et propre à l'utilisateur en brownfield) en dernier.
    for rel in (".claude/CLAUDE.md", "README.md", ".env.example", ".claude/docs/stack.md",
                ".claude/docs/cadrage/README.md", ".claude/docs/HANDOFF.md", "CLAUDE.md"):
        b, o = raw_base / rel, project / rel
        if not (b.is_file() and o.is_file()):
            continue
        bl = b.read_text(encoding="utf-8", errors="replace").split("\n")
        ol = o.read_text(encoding="utf-8", errors="replace").split("\n")
        sm = difflib.SequenceMatcher(None, bl, ol, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "replace":
                continue
            for bline, oline in zip(bl[i1:i2], ol[j1:j2]):
                names = CORE_RE.findall(bline)
                if not names:
                    continue
                pattern, seen = "", {}
                for part in re.split(r"(\{\{[A-Z]{2,}_[A-Z][A-Z0-9_]+\}\})", bline):
                    m = CORE_RE.fullmatch(part)
                    if m:
                        name = m.group(1)
                        if name in seen:
                            pattern += f"(?P={seen[name]})"
                        else:
                            seen[name] = f"g{len(seen)}"
                            pattern += f"(?P<{seen[name]}>.+?)"
                    else:
                        pattern += re.escape(part)
                mm = re.fullmatch(pattern, oline)
                if not mm:
                    continue
                for name, g in seen.items():
                    val = mm.group(g).strip()
                    if val and "{{" not in val:
                        found.setdefault(name, val)
    return found


def teams_in_use(project: Path, settings: dict) -> bool:
    """Le plugin agent-teams est-il activé pour ce projet (settings projet, local ou user) ?"""
    sources = [settings]
    user_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    for p in (project / ".claude" / "settings.local.json", user_dir / "settings.json"):
        try:
            sources.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    for s in sources:
        ep = s.get("enabledPlugins") if isinstance(s, dict) else None
        if isinstance(ep, dict) and any(k.startswith("agent-teams@") and v for k, v in ep.items()):
            return True
    return False


# ── Fusions ──────────────────────────────────────────────────────────────────────────────────

def merge_text(ours: bytes, base: bytes, theirs: bytes, tmp: Path):
    """git merge-file (3 voies). Retourne (contenu fusionné, conflit ?)."""
    d = Path(tempfile.mkdtemp(dir=tmp, prefix="m3-"))
    o, b, t = d / "ours", d / "base", d / "theirs"
    o.write_bytes(ours)
    b.write_bytes(base)
    t.write_bytes(theirs)
    r = subprocess.run(["git", "merge-file", "-p", "-L", "projet", "-L", "base", "-L", "template",
                        str(o), str(b), str(t)], capture_output=True)
    shutil.rmtree(d, ignore_errors=True)
    if r.returncode < 0 or r.returncode > 127:
        return None, True
    return r.stdout, r.returncode != 0


def merge_value(o, b, t, path: str, notes: list, protect: set):
    """Fusion 3 voies d'une valeur JSON (dicts récursifs ; le reste = atome)."""
    if isinstance(o, dict) and (b is MISSING or isinstance(b, dict)) \
            and (t is MISSING or isinstance(t, dict)) and not (b is MISSING and t is MISSING):
        bd = b if isinstance(b, dict) else {}
        td = t if isinstance(t, dict) else {}
        out = {}
        for k in list(td.keys()) + [k for k in o.keys() if k not in td]:
            v = merge_value(o.get(k, MISSING), bd.get(k, MISSING), td.get(k, MISSING),
                            f"{path}.{k}" if path else k, notes, protect)
            if v is not MISSING:
                out[k] = v
        if not out and t is MISSING:
            return MISSING  # objet entièrement retiré en amont (et rien d'ajouté ici)
        return out
    if o == t:
        return o
    if path in protect:  # clé à garder telle quelle (ex. flag d'équipe d'un projet qui l'utilise)
        if o is not MISSING:
            notes.append(f"settings `{path}` conservé (équipe d'agents active sur ce projet)")
        return o
    if o == b:
        if t is MISSING:
            extra = (" — les agent teams sont opt-in : `/plugin install agent-teams@claude-setup` puis "
                     "`/agent-teams:team` pour les réactiver") if path in (f"env.{TEAM_ENV}", "teammateMode") else ""
            notes.append(f"settings `{path}` retiré (retiré du template){extra}")
        elif b is MISSING:
            notes.append(f"settings `{path}` ajouté")
        else:
            notes.append(f"settings `{path}` mis à jour")
        return t
    if t == b:
        return o  # personnalisation du projet, template inchangé
    notes.append(f"⚠️ settings `{path}` : personnalisé ici ET modifié en amont → valeur du projet gardée "
                 f"(template : {json.dumps(None if t is MISSING else t, ensure_ascii=False)})")
    return o


def _hook_id(h) -> str:
    """Identité d'un handler : tout le handler sauf ses réglages (timeout, statusMessage). Un hook
    `prompt` / `agent` / `http` / `mcp_tool` n'a pas de `command`, et deux handlers peuvent partager
    une commande avec des `if` différents : la commande seule ne suffit pas (hooks perdus avant)."""
    if not isinstance(h, dict):
        return json.dumps(h, sort_keys=True, ensure_ascii=False)
    return json.dumps({k: v for k, v in h.items() if k not in ("timeout", "statusMessage")},
                      sort_keys=True, ensure_ascii=False)


def _flat_hooks(s: dict) -> dict:
    """{(événement, signature du groupe, identité du handler, n° d'occurrence): (groupe sans hooks, handler)}."""
    out = {}
    hooks = s.get("hooks") if isinstance(s, dict) else None
    for ev, groups in (hooks or {}).items():
        for g in groups or []:
            if not isinstance(g, dict):
                continue
            gmeta = {k: v for k, v in g.items() if k != "hooks"}
            gsig = json.dumps(gmeta, sort_keys=True, ensure_ascii=False)
            for h in g.get("hooks") or []:
                base = (ev, gsig, _hook_id(h))
                n = 0
                while base + (n,) in out:
                    n += 1
                out[base + (n,)] = (gmeta, h)
    return out


def _hook_label(key) -> str:
    ev, gsig = key[0], json.loads(key[1])
    m = gsig.get("matcher")
    return f"{ev}" + (f" ({m})" if m else "")


def merge_settings(o: dict, b: dict, t: dict, notes: list, protect: set, additive: bool = False) -> dict:
    """Fusion 3 voies de settings.json. `additive` (projet adopté/brownfield) : une règle ou un hook
    du template absent du projet est AJOUTÉ (l'adoption fusionnait à la main, rien ne prouve un
    retrait volontaire) ; en greenfield, un élément du template retiré par le projet reste retiré."""
    res = {}
    keys = list(t.keys()) + [k for k in o.keys() if k not in t]
    for k in keys:
        if k == "permissions":
            op, bp, tp = o.get(k) or {}, b.get(k) or {}, t.get(k) or {}
            perms = {}
            for kind in list(tp.keys()) + [x for x in op.keys() if x not in tp]:
                ol, bl, tl = op.get(kind), bp.get(kind), tp.get(kind)
                if not all(isinstance(x, list) for x in (ol or [], bl or [], tl or [])):
                    perms[kind] = merge_value(op.get(kind, MISSING), bp.get(kind, MISSING),
                                              tp.get(kind, MISSING), f"permissions.{kind}", notes, protect)
                    continue
                ol, bl, tl = ol or [], bl or [], tl or []
                removed = [x for x in bl if x not in tl]
                added = [x for x in tl if x not in bl]
                # ordre du template (règles gardées ou nouvelles), puis les ajouts propres au projet
                new = [x for x in tl if x in ol or x in added or additive] + \
                      [x for x in ol if x not in tl and x not in removed]
                if additive and [x for x in tl if x not in ol and x not in added]:
                    notes.append(f"permissions.{kind} : {len([x for x in tl if x not in ol and x not in added])} "
                                 "règle(s) du template ajoutée(s) (projet adopté : absentes)")
                gone = [x for x in ol if x in removed]
                if gone:
                    notes.append(f"permissions.{kind} : {len(gone)} règle(s) retirée(s) par le template")
                if [x for x in added if x not in ol]:
                    notes.append(f"permissions.{kind} : {len([x for x in added if x not in ol])} règle(s) ajoutée(s)")
                if new or kind in op or kind in tp:
                    perms[kind] = new
            res[k] = perms
        elif k == "hooks":
            fo, fb, ft = _flat_hooks(o), _flat_hooks(b), _flat_hooks(t)
            merged = {}
            for key in list(ft.keys()) + [x for x in fo.keys() if x not in ft]:
                if key in fb and key not in ft:  # retiré en amont
                    if key in fo and fo[key] != fb[key]:
                        merged[key] = fo[key]
                        notes.append(f"⚠️ hook {_hook_label(key)} personnalisé, retiré du template → gardé")
                    elif key in fo:
                        notes.append(f"hook {_hook_label(key)} retiré")
                    continue
                if key not in fo:
                    if key in fb and not additive:  # retiré volontairement par le projet → on respecte
                        if ft.get(key) != fb[key]:
                            notes.append(f"⚠️ hook {_hook_label(key)} retiré ici mais modifié en amont → laissé retiré")
                        continue
                    merged[key] = ft[key]  # nouveau en amont (ou projet adopté : fusion additive)
                    notes.append(f"hook {_hook_label(key)} ajouté")
                    continue
                if key in ft and key in fb and fo[key] == fb[key]:
                    merged[key] = ft[key]  # réglages (timeout…) mis à jour
                else:
                    merged[key] = fo[key]  # propre au projet, ou personnalisé : jamais perdu
            hooks = {}
            for key, (gmeta, h) in merged.items():
                ev, gsig = key[0], key[1]
                groups = hooks.setdefault(ev, [])
                grp = next((g for g in groups if g["__sig"] == gsig), None)
                if grp is None:
                    grp = dict(gmeta, hooks=[], __sig=gsig)
                    groups.append(grp)
                grp["hooks"].append(h)
            for groups in hooks.values():
                for g in groups:
                    del g["__sig"]
            if hooks or "hooks" in o:
                res[k] = hooks
        else:
            v = merge_value(o.get(k, MISSING), b.get(k, MISSING), t.get(k, MISSING), k, notes, protect)
            if v is not MISSING:
                res[k] = v
    return res


# ── Migrations de la doc projet (versionnées, idempotentes) ─────────────────────────────────

def migrate_1_4_0(project: Path, raw_target: Path, dry: bool, log: list):
    slim = raw_target / ".claude" / "skills" / "init-from-template" / "scripts" / "slim-context.py"
    if not slim.is_file():
        log.append("migration 1.4.0 : slim-context.py introuvable dans la cible — sautée")
        return
    args = [sys.executable, str(slim), "--root", str(project), "--no-template-files"]
    if dry:
        args.append("--dry-run")
    r = sh(args, check=False)
    done = [l.strip() for l in r.stdout.splitlines() if "✅" in l]
    log.append("migration 1.4.0 (budget de contexte : journal HANDOFF, gotchas, ROADMAP) : "
               + (f"{len(done)} étape(s) — " + " | ".join(done) if done else "rien à faire"))


HANDOFF_TEAM_NOTE = re.compile(r"^> 🧑‍🤝‍🧑 \*\*Multi-agent / agent teams\*\* : fichier partagé.*\n", re.M)


def migrate_1_5_0(project: Path, raw_target: Path, dry: bool, log: list):
    # Les skills v1.4.x (/debug, /feature-done, protocole d'équipe) écrivaient encore des gotchas dans
    # code-map.md (auto-chargée) : on rejoue la migration du budget (idempotente) pour les sortir.
    if not any(m.startswith("migration 1.4.0") for m in log):  # pas deux fois dans le même upgrade
        migrate_1_4_0(project, raw_target, dry, log)
    ho = project / ".claude" / "docs" / "HANDOFF.md"
    if ho.is_file():
        text = ho.read_text(encoding="utf-8")
        new = HANDOFF_TEAM_NOTE.sub("", text)
        if new != text:
            if not dry:
                ho.write_text(new, encoding="utf-8")
            log.append("migration 1.5.0 : HANDOFF.md — note multi-agent du gabarit retirée "
                       "(contredisait la rule d'équipe, ligne auto-chargée)")
            return
    log.append("migration 1.5.0 : rien à faire")


MIGRATIONS = [("1.4.0", migrate_1_4_0), ("1.5.0", migrate_1_5_0)]


# ── Moteur ───────────────────────────────────────────────────────────────────────────────────

def unsafe_path(project: Path, rel: str) -> bool:
    """Écrire/supprimer `rel` traverserait-il un lien symbolique, ou sortirait-il du projet ?
    (ex. `.claude/rules` lié à un dossier partagé : l'upgrade réécrivait des fichiers HORS du projet,
    invisibles pour son git — donc irrécupérables par `git revert`)."""
    p = project
    for part in Path(rel).parts:
        p = p / part
        if p.is_symlink():
            return True
    try:
        (project / rel).resolve().relative_to(project.resolve())
    except ValueError:
        return True
    return False


def git_dirty(project: Path):
    if not is_git_repo(project):
        return []
    out = sh(["git", "-C", str(project), "status", "--porcelain", "--", ".",
              ":(exclude).claude/.cache"], check=False).stdout
    return [l for l in out.splitlines() if l.strip()]


def plan_and_apply(a) -> dict:
    project = Path(a.project).resolve()
    if not (project / ".claude").is_dir():
        raise UpgradeError(f"{project} : pas de .claude/ — pas un projet généré depuis le template")
    lock_path = project / ".claude" / "template-lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        lock = {}
    from_v = a.from_version
    tv = project / ".claude" / "template-version"
    if not from_v and tv.is_file():
        from_v = tv.read_text(encoding="utf-8").strip()
    if not from_v:
        raise UpgradeError("version du projet inconnue (.claude/template-version absent) → préciser --from X.Y.Z")
    if not a.dry_run and not a.allow_dirty:
        dirty = git_dirty(project)
        if dirty:
            raise UpgradeError("arbre git non propre — committer ou stasher d'abord (le diff de mise à jour "
                               "doit être relisible seul), ou --allow-dirty :\n  " + "\n  ".join(dirty[:10]))

    tmp = Path(tempfile.mkdtemp(prefix="upgrade-template-"))
    report = {"project": str(project), "from": from_v, "to": None, "profile": None, "dry_run": a.dry_run,
              "actions": [], "settings": [], "migrations": [], "warnings": [], "conflicts": [],
              "vars": {}, "status": None}
    try:
        source = a.template or lock.get("source") or DEFAULT_SOURCE
        repo = open_template(source, tmp)
        to_ref = a.to or latest_tag(repo) or "WORKTREE"
        raw_t = tmp / "raw-target"
        if not extract(repo, to_ref, raw_t):
            raise UpgradeError(f"version cible introuvable dans le template : {to_ref}")
        tvt = raw_t / ".claude" / "template-version"
        if not tvt.is_file():
            raise UpgradeError(f"{to_ref} n'est pas une version du template claude-Setup (pas de .claude/template-version)")
        to_v = tvt.read_text(encoding="utf-8").strip()
        report["to"] = to_v
        pending = [c for c in lock.get("pending_conflicts", []) if isinstance(c, str)]
        if vtuple(from_v) == vtuple(to_v) and not a.force:
            if pending and not a.ack_conflicts:
                report["conflicts"] = pending
                report["status"] = f"à jour — {len(pending)} conflit(s) en attente de la mise à jour précédente"
                report["warnings"].append("Résoudre chaque fichier (version cible : .claude/.cache/upgrade-"
                                          f"{to_v}/<fichier>.template si présent), puis relancer avec --ack-conflicts")
                return report
            if pending and a.ack_conflicts and not a.dry_run:
                lock.pop("pending_conflicts", None)
                lock_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                report["warnings"].append(f"{len(pending)} conflit(s) marqué(s) résolu(s)")
            report["status"] = "à jour"
            return report
        if pending:
            report["warnings"].append("conflits NON résolus de la mise à jour précédente (traités ici comme des "
                                      "personnalisations) : " + ", ".join(pending))
        if vtuple(from_v) > vtuple(to_v) and not a.force:
            raise UpgradeError(f"le projet ({from_v}) est plus récent que la cible ({to_v}) — rien à faire")

        profile = a.profile or lock.get("profile") or infer_profile(project)
        if profile not in PROFILES:
            raise UpgradeError(f"profil inconnu : {profile}")
        report["profile"] = profile + ("" if (a.profile or lock.get("profile")) else " (déduit)")
        # Adopté (/adopt-template) : le lock le dit ; sans lock (< 1.5), un skill bootstrap encore
        # présent le trahit — l'init greenfield les retire toujours, l'adoption les laisse.
        stack = project / ".claude" / "docs" / "stack.md"
        adopted_mark = stack.is_file() and "adopté le" in stack.read_text(encoding="utf-8", errors="replace")
        # L'init greenfield PURGE les lignes d'inventaire des skills bootstrap ; l'adoption (brownfield)
        # les laisse — un indice qui survit au retrait des skills bootstrap eux-mêmes.
        for idx in (".claude/USAGE.md", ".claude/CLAUDE.md", ".claude/rules/template-maintenance.md"):
            f = project / idx
            if f.is_file() and re.search(r"^\s*[-|].*`/(adopt-template|init-from-template)",
                                         f.read_text(encoding="utf-8", errors="replace"), re.M):
                adopted_mark = True
        if a.mode:
            brownfield = a.mode == "brownfield"
        else:
            brownfield = lock.get("mode") == "brownfield" or (not lock and (adopted_mark or any(
                (project / ".claude" / "skills" / s).is_dir() for s in ("adopt-template", "init-from-template"))))
        # Fusion additive (hooks/règles du template absents du projet → ajoutés) : UNIQUEMENT à la
        # 1re mise à jour d'un projet adopté sans lock (< 1.5, fusion manuelle à l'adoption). Ensuite,
        # sémantique 3 voies stricte — sinon un retrait volontaire (ex. Edit(./**)) revenait à chaque fois.
        additive = brownfield and not lock

        raw_b = tmp / "raw-base"
        has_base = extract(repo, f"v{from_v}", raw_b) if is_git_repo(repo) else False
        if not has_base and vtuple(from_v) == vtuple(to_v):
            # --force sur la même version (tag pas encore publié) : la cible EST la base
            shutil.rmtree(raw_b, ignore_errors=True)
            shutil.copytree(raw_t, raw_b)
            has_base = True
        if not has_base:
            report["warnings"].append(f"tag v{from_v} introuvable dans le template → mode prudent : toute "
                                      "différence avec la cible est traitée comme une personnalisation")
        vars_ = {}  # jamais stockées (PII : noms, emails) — redéduites des fichiers rendus à chaque fois
        if has_base:
            for k, v in infer_vars(raw_b, project).items():
                vars_.setdefault(k, v)
        report["vars"] = sorted(vars_)

        base = tmp / "base"
        target = tmp / "target"
        if has_base:
            replay_init(raw_b, base, profile, brownfield, vars_, report["warnings"])
        else:
            base.mkdir()
        replay_init(raw_t, target, profile, brownfield, vars_, report["warnings"])
        report["mode"] = "brownfield" if brownfield else "greenfield"

        try:
            o_settings = json.loads((project / ".claude" / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            o_settings = {}
        teams = teams_in_use(project, o_settings)
        protect = {f"env.{TEAM_ENV}", "teammateMode"} if teams else set()
        team_rule_src = raw_t.parent / "team-rule.md"
        if teams:
            src_rule = (repo / TEAM_RULE_SRC) if to_ref == "WORKTREE" else None
            content = src_rule.read_bytes() if src_rule and src_rule.is_file() else \
                sh(["git", "-C", str(repo), "show", f"{to_ref}:{TEAM_RULE_SRC}"], check=False).stdout.encode() \
                if is_git_repo(repo) else b""
            if content:
                team_rule_src.write_bytes(content)
            report["warnings"].append("équipe d'agents active (plugin agent-teams) : flag, teammateMode et "
                                      "rule d'équipe conservés — rule mise à jour depuis le plugin")

        conflict_dir = project / ".claude" / ".cache" / f"upgrade-{to_v}"
        paths = sorted(scoped_files(base) | scoped_files(target) | scoped_files(project))
        writes, deletes = {}, []
        for rel in paths:
            B = read_bytes(base / rel) if has_base else None
            T = read_bytes(target / rel)
            O = read_bytes(project / rel)
            if rel == TEAM_RULE and teams and team_rule_src.is_file():
                T = team_rule_src.read_bytes()  # la rule d'équipe vient du plugin (projet équipé)
            if O == T:
                continue
            if B is None and T is None:
                continue  # fichier propre au projet (skill, hook, rule maison) — jamais touché
            if O is None and rel.startswith(BOOTSTRAP_PREFIXES):
                continue  # skills bootstrap retirés après adoption (proposé par /adopt-template) : respecté
            if rel == ".claude/settings.json" and O is not None and T is not None:
                try:
                    oj = json.loads(O)
                    bj = json.loads(B) if B else {}
                    tj = json.loads(T)
                except ValueError:
                    oj = bj = tj = None
                if oj is None or not isinstance(oj, dict):  # JSON du projet invalide → jamais écrasé
                    report["actions"].append({"path": rel, "action": "conflict",
                                              "detail": "settings.json du projet illisible (JSON invalide) — gardé"})
                    report["conflicts"].append(rel)
                    writes[f"__aside__/{rel}.template"] = T
                    continue
                if tj is not None:
                    notes = []
                    merged = merge_settings(oj, bj, tj, notes, protect, additive=additive)
                    out = (json.dumps(merged, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                    report["settings"] = notes
                    if out != O:
                        writes[rel] = out
                        report["actions"].append({"path": rel, "action": "merge-json"})
                    continue
            if B == O:  # le projet n'y a pas touché → la cible s'applique
                if T is None:
                    deletes.append(rel)
                    report["actions"].append({"path": rel, "action": "remove"})
                else:
                    writes[rel] = T
                    report["actions"].append({"path": rel, "action": "add" if O is None else "update"})
                continue
            if B == T and B is not None:  # template inchangé → personnalisation gardée
                report["actions"].append({"path": rel, "action": "keep-custom"})
                continue
            if O is None:
                if B is None:  # nouveau fichier du template (mode prudent inclus)
                    writes[rel] = T
                    report["actions"].append({"path": rel, "action": "add"})
                else:  # supprimé ici, modifié en amont
                    report["actions"].append({"path": rel, "action": "conflict",
                                              "detail": "supprimé dans le projet, modifié dans le template"})
                    report["conflicts"].append(rel)
                    writes[f"__aside__/{rel}.template"] = T
                continue
            if T is None:  # retiré en amont mais modifié ici
                report["actions"].append({"path": rel, "action": "conflict",
                                          "detail": "modifié dans le projet, retiré du template — gardé"})
                report["conflicts"].append(rel)
                continue
            if B is None:  # créé des deux côtés (ou base inconnue)
                report["actions"].append({"path": rel, "action": "conflict",
                                          "detail": "diffère de la cible (pas de base commune)"})
                report["conflicts"].append(rel)
                writes[f"__aside__/{rel}.template"] = T
                continue
            merged, conflicted = merge_text(O, B, T, tmp)
            if merged is not None and not conflicted:
                writes[rel] = merged
                report["actions"].append({"path": rel, "action": "merge"})
            else:
                report["actions"].append({"path": rel, "action": "conflict",
                                          "detail": "modifié des deux côtés, fusion impossible"})
                report["conflicts"].append(rel)
                writes[f"__aside__/{rel}.template"] = T
                if merged is not None:
                    writes[f"__aside__/{rel}.merge"] = merged

        # Chemins traversant un lien symbolique : jamais modifiés, signalés en conflit
        for rel in [r for r in list(writes) if not r.startswith("__aside__/")] + list(deletes):
            if unsafe_path(project, rel):
                content = writes.pop(rel, None)
                if rel in deletes:
                    deletes.remove(rel)
                for x in report["actions"]:
                    if x["path"] == rel:
                        x["action"], x["detail"] = "conflict", "passe par un lien symbolique (hors projet) — non modifié"
                report["conflicts"].append(rel)
                if content is not None:
                    writes[f"__aside__/{rel}.template"] = content

        # Application
        if not a.dry_run:
            aside_ok = not unsafe_path(project, conflict_dir.relative_to(project).as_posix())
            for rel, content in writes.items():
                if rel.startswith("__aside__/") and not aside_ok:
                    continue
                dst = conflict_dir / rel[len("__aside__/"):] if rel.startswith("__aside__/") else project / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(content)
                src_mode = (target / rel).stat().st_mode if (target / rel).is_file() else None
                if src_mode and not rel.startswith("__aside__/"):
                    dst.chmod(src_mode & 0o777)
            for rel in deletes:
                try:
                    (project / rel).unlink()
                except OSError:
                    pass
                parent = (project / rel).parent  # dossier de skill vidé → retiré
                while parent != project and parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent

        # Migrations de la doc projet (après les fichiers de méthode — idempotentes)
        for v, fn in MIGRATIONS:
            if vtuple(from_v) < vtuple(v) <= vtuple(to_v):
                fn(project, raw_t, a.dry_run, report["migrations"])

        if not a.dry_run:
            lock.update({"template": "claude-Setup", "version": to_v, "profile": profile,
                         "mode": "brownfield" if brownfield else "greenfield",
                         "upgraded": date.today().isoformat()})
            if re.match(r"^(https?://|git@|ssh://)", source):
                lock["source"] = source
            lock.setdefault("source", DEFAULT_SOURCE)
            if report["conflicts"]:
                lock["pending_conflicts"] = sorted(set(report["conflicts"]))
            else:
                lock.pop("pending_conflicts", None)
            lock_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            if report["conflicts"]:
                (conflict_dir / "REPORT.md").parent.mkdir(parents=True, exist_ok=True)
                (conflict_dir / "REPORT.md").write_text(render_report(report), encoding="utf-8")
        report["status"] = ("plan (dry-run)" if a.dry_run else "appliqué") + \
            (f" — {len(report['conflicts'])} conflit(s)" if report["conflicts"] else "")
        return report
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def render_report(r: dict) -> str:
    counts = {}
    for x in r["actions"]:
        counts[x["action"]] = counts.get(x["action"], 0) + 1
    lines = [f"# Mise à jour claude-Setup {r['from']} → {r['to']}" + (" (dry-run)" if r["dry_run"] else ""),
             "", f"Profil : {r['profile']} · mode : {r.get('mode', '?')} · statut : {r['status']}", ""]
    labels = {"update": "mis à jour", "add": "ajoutés", "remove": "retirés", "merge": "fusionnés (3 voies)",
              "merge-json": "settings fusionnés", "keep-custom": "personnalisations gardées (template inchangé)",
              "conflict": "CONFLITS"}
    for k in ("update", "add", "remove", "merge", "merge-json", "keep-custom", "conflict"):
        if counts.get(k):
            lines.append(f"## {labels[k]} ({counts[k]})")
            for x in r["actions"]:
                if x["action"] == k:
                    lines.append(f"- `{x['path']}`" + (f" — {x['detail']}" if x.get("detail") else ""))
            lines.append("")
    if r["settings"]:
        lines += ["## settings.json", *[f"- {n}" for n in r["settings"]], ""]
    if r["migrations"]:
        lines += ["## Migrations de la doc projet", *[f"- {m}" for m in r["migrations"]], ""]
    if r["warnings"]:
        lines += ["## Avertissements", *[f"- {w}" for w in r["warnings"]], ""]
    if r["conflicts"]:
        lines += ["## Résoudre les conflits",
                  f"Pour chaque fichier : version cible = `.claude/.cache/upgrade-{r['to']}/<fichier>.template`, "
                  "merge annoté (si possible) = `<fichier>.merge`. Le fichier du projet n'a PAS été modifié.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".")
    ap.add_argument("--template", default=None)
    ap.add_argument("--to", default=None)
    ap.add_argument("--from", dest="from_version", default=None)
    ap.add_argument("--profile", default=None, choices=PROFILES)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--force", action="store_true", help="rejouer même si la version est identique")
    ap.add_argument("--mode", choices=("greenfield", "brownfield"), default=None,
                    help="forcer le mode d'init d'origine (défaut : lock, sinon déduit)")
    ap.add_argument("--ack-conflicts", action="store_true",
                    help="marquer résolus les conflits en attente de la mise à jour précédente")
    a = ap.parse_args()
    try:
        report = plan_and_apply(a)
    except Exception as e:  # noqa: BLE001 — code 2 « erreur » quoi qu'il arrive (1 = conflits)
        if a.json:
            print(json.dumps({"status": "erreur", "error": str(e)}, ensure_ascii=False))
        else:
            print(f"❌ {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["status"] == "à jour":
        print(f"✅ Projet déjà à jour (claude-Setup {report['from']}).")
    else:
        print(render_report(report))
    return 1 if report["conflicts"] else 0


if __name__ == "__main__":
    sys.exit(main())
