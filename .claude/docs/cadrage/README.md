# Cadrage — {{PROJECT_NAME}}

> Ce dossier contient **tout ce qui sert à comprendre/définir le projet** + ses évolutions.
> Ce README est la **synthèse vivante** ; le détail brut est dans `tickets/`, `documents/`, `reunions/`.
>
> ⚠️ **Document vivant** : MAJ à chaque nouvelle réunion, ticket, pivot, accès accordé.
> Si pivot demandé par hiérarchie → réunion dans `reunions/YYYY-MM-DD-pivot.md` + MAJ ce README.

**Date kickoff :** {{YYYY-MM-DD}}
**Demandeur :** {{NOM, RÔLE, ENTREPRISE}}
**Canal initial :** {{Mail / Réunion / Slack / Ticket}}
**Tickets liés :** {{[TICKET-XXX](tickets/TICKET-XXX-...md)}}
**Docs reçus :** voir [documents/](documents/)

## Interlocuteurs

| Nom       | Rôle     | Contact   | Pour quoi                              |
| --------- | -------- | --------- | -------------------------------------- |
| {{Nom 1}} | {{Rôle}} | {{email}} | {{validation business / accès / etc.}} |
| {{Nom 2}} | {{Rôle}} | {{email}} | ...                                    |
| ...       | ...      | ...       | ...                                    |

**Décisionnaire final :** {{Nom — qui valide les décisions scope/archi/planning}}
**Cadence :** {{point hebdo + canal Slack/Teams}}

> Pour les gros projets (> 5 stakeholders, plusieurs équipes), promouvoir dans un fichier `STAKEHOLDERS.md` dédié au niveau `docs/`.

## Demande exprimée (verbatim)

> {{Coller ici la demande EXACTE du client — mail, retranscription verbatim
> d'une réunion, ou copy/paste du ticket.}}
>
> {{Garder le ton/style original — pas reformuler. Le but c'est de capter
> ce qu'il a VRAIMENT dit, pas ce que toi tu en comprends.}}
>
> — {{Source : mail du JJ/MM, réunion du JJ/MM, etc.}}

## Contexte

- **{{Système source}}** : {{type, version, accès}}
- **{{Système destination}}** : {{...}}
- **Volume** : {{X entités/jour, pics estimés}}
- **Fréquence souhaitée** : {{temps réel / X min / batch journalier / ...}}
- **Existant** : {{ce qui tourne déjà / ce qu'on remplace}}

## Contraintes

- **Budget** : {{forfait défini / TJM / à discuter}}
- **Sécurité** : {{credentials lecture seule / RGPD / etc.}}
- **Délai** : {{MVP cible YYYY-MM-DD}}
- **Hébergement** : {{on-premise / cloud / contrainte spécifique}}
- **Techniques** : {{stack imposée / interdite}}

## Ce qui N'EST PAS demandé (out of scope)

- {{Item 1 — out of scope explicite}}
- {{Item 2 — peut-être v2}}
- {{Item 3}}

## Risques identifiés au kickoff

- {{Risque 1 — ex: API tierce instable}}
- {{Risque 2 — ex: rate limit / VPN flaky}}
- {{Risque 3}}

## Suite

- [ ] Brief validé par {{décideur}} le {{date}}
- [ ] PRD à écrire (`../conception/PRD.md`), validation attendue avant {{date}}
- [ ] ARCHITECTURE après validation PRD (`../conception/ARCHITECTURE.md`)

---

## Comment ce dossier est organisé

```
cadrage/
├── README.md         ← ce fichier (la synthèse vivante)
├── tickets/          ← tickets Jira/Linear/Asana reçus
├── documents/        ← docs client (PDF, Excel, captures)
├── reunions/         ← comptes-rendus de réunions (incl. pivots)
└── diagrams/         ← schémas business (ASCII + Excalidraw/SVG si gros)
```

**Le README synthétise** ; le reste contient le **matériel brut** pour traçabilité.

**Pour les diagrammes** : convention détaillée dans [diagrams/README.md](diagrams/README.md). En 2 mots : ASCII inline par défaut, Excalidraw + export SVG si gros.
