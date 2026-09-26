# tdd — comportements spécifiables A PRIORI (logique métier, parsing, contrats d'API, calculs)

> Planifier → Écrire les tests (rouges) → Coder (vert) → Review adverse → Vérifier → Persister

1. **Planifier** — action : `/spec "<titre>"` puis `/conception <id>` (qui note « TDD » dans `plan.md § Décisions`) — sortie : plan gelé, comportements attendus listés et testables
2. **Écrire les tests** — action : rédiger les tests des comportements AVANT tout code (solo ; en équipe : rôle `tester` d'abord, tasks d'implémentation **bloquées** dessus — mode TDD de `/agent-teams:team`) — sortie : tests écrits, **ROUGES pour la bonne raison** (le comportement manque, pas une typo)
3. **Coder** — action : faire passer au vert test par test, **sans modifier les tests** (un test rouge légitime = rapport/discussion, on ne le tord pas) — sortie : suite verte
4. **Review adverse** — action : subagent `reviewer` sur le diff — code **ET** tests (un test complaisant ou tautologique = un finding) — sortie : findings 🔴 corrigés
5. **Vérifier** — action : suite complète + DoD de la spec — sortie : tout vert, DoD rempli
6. **Persister** — action : `/feature-done <id>` (+ `/lecon` si pièges) — sortie : ROADMAP cochée, CHANGELOG, HANDOFF à jour
