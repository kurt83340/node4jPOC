# standard — feature classique (comportements découverts en codant, UI mouvante, intégration à explorer)

> Planifier → Coder → Tester → Review adverse → Vérifier → Persister

1. **Planifier** — action : `/spec "<titre>"` puis `/conception <id>` — sortie : `plan.md` gelé (revue adverse passée) + `tasks.md` partitionné par fichiers
2. **Coder** — action : solo (tasks une à une, cochées au fil) ou `/agent-teams:team <id>` (plugin, dès 2+ groupes parallélisables) — sortie : tasks cochées, code sur branche `feature/<id>`
3. **Tester** — action : écrire/compléter les tests des comportements livrés + lancer la suite — sortie : suite verte
4. **Review adverse** — action : subagent `reviewer` sur `git diff` (contexte frais, il n'a pas vu la genèse) — sortie : findings 🔴 corrigés, 🟠 arbitrés avec l'utilisateur
5. **Vérifier** — action : suite complète + DoD de la spec relu ligne à ligne — sortie : tout vert, DoD rempli (sinon retour étape 2)
6. **Persister** — action : `/feature-done <id>` (+ `/lecon` si pièges rencontrés) — sortie : ROADMAP cochée, CHANGELOG, HANDOFF à jour
