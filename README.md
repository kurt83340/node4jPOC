# {{PROJECT_NAME}}

{{1-2 phrases description}}

> 🚀 **Tu débutes avec ce template ?** Lis [USAGE.md](.claude/USAGE.md) section "Setup d'un nouveau projet" (étapes 1 à 6 + `/init-from-template`).
> 📐 **Convention complète** : [STRUCTURE.md](.claude/STRUCTURE.md) (arborescence, naming, patterns).

## Stack

- {{Langage principal + version}}
- {{Frameworks majeurs}}
- {{Services tiers}}

→ Détails complets : [.claude/docs/stack.md](.claude/docs/stack.md)

## Setup local

```bash
# 1. Cloner et créer venv
git clone <repo>
cd {{PROJECT_FOLDER}}
{{COMMANDE_INSTALL}}  # uv pip install -r requirements.txt | npm install | etc.

# 2. Variables d'env
cp .env.example .env
# Remplir les valeurs (voir .claude/docs/ACCESS.md pour les obtenir)

# 3. Garde-fou secrets (une fois par clone) — gitleaks en pre-commit
pre-commit install   # prérequis : pipx install pre-commit (ou uv tool install pre-commit)

# 4. Tests
{{COMMANDE_TESTS}}  # pytest | npm test | etc.

# 5. Lancer en local
{{COMMANDE_RUN}}  # python src/main.py | npm run dev | etc.
```

## Déploiement

Voir [.claude/docs/RUNBOOK.md](.claude/docs/RUNBOOK.md) (créé au 1er déploiement prod).

## Documentation projet

Toute la doc dans [.claude/docs/](.claude/docs/) :

- Cadrage + interlocuteurs : [.claude/docs/cadrage/README.md](.claude/docs/cadrage/README.md)
- Architecture : [.claude/docs/conception/ARCHITECTURE.md](.claude/docs/conception/ARCHITECTURE.md)
- Roadmap : [.claude/docs/ROADMAP.md](.claude/docs/ROADMAP.md)

## Contact

- Owner technique : {{TON_NOM}} ({{TON_EMAIL}})
- Owner business {{CLIENT_NAME}} : {{NOM_DECIDEUR}} ({{EMAIL_DECIDEUR}})

---

> 💡 Ce projet utilise le **[template Claude Code](.claude/STRUCTURE.md)** (convention 2026). Usage quotidien : [USAGE.md](.claude/USAGE.md). Exemple rempli : [EXAMPLES/acme-sync-erp-notion-docs/](EXAMPLES/acme-sync-erp-notion-docs/).
