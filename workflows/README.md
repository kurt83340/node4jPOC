# workflows/ — Exports n8n

JSON exports des workflows n8n pour versionning et restoration.

## Convention de naming

- `sync-erp.json` : workflow principal de sync ERP→Notion (prod)
- `sync-erp-staging.json` : version staging si différente
- `_archive/` : anciennes versions (pour historique, optionnel)

## Comment exporter depuis n8n

```bash
# Via API
curl -X GET "https://n8n.acme.local/api/v1/workflows/<id>/export" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  > workflows/sync-erp.json
```

Ou via UI n8n : Workflow > 3 dots > Download.

## Comment réimporter

```bash
# Via API (ex. depuis un skill de déploiement projet, ou l'UI n8n)
curl -X POST "https://n8n.acme.local/api/v1/workflows/import" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflows/sync-erp.json
```

⚠️ **Les credentials ne sont PAS dans le JSON** (sécurité). À reconfigurer manuellement dans n8n après import.

## Versioning

Chaque commit dans `workflows/*.json` doit avoir une entrée CHANGELOG correspondante. Le tag git (`vYYYY.MM.DD-HHMM`) référence l'état de tous les workflows à ce moment.

Pour restore une version précédente :

```bash
git show v2026.05.20-1000:workflows/sync-erp.json > /tmp/restore.json
# puis import via UI ou API
```
