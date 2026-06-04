# frappe_vault — Claude Code Context

**Load at session start:** `../FRAPPE_AI_DEV_GUIDE.md` sections 1, 2, 3, 18, 20. See Appendix F for active tasks.

## App identity
- Name: frappe_vault
- Title: Frappe Vault
- Purpose: Secure unified file serving — local disk and S3-compatible (Hetzner) storage
- Repo: https://github.com/countynetkenya/frappe_vault
- Server path: /home/ubuntu/ERPNext/staging/apps/frappe_vault/

## S3 Config
- Provider: Hetzner
- Endpoint: fsn1.your-objectstorage.com
- Bucket: skillwave

## Active bugs (fix first)
1. `add_to_apps_screen` has None value in hooks.py → desktop icon crash

## Architecture
- Overrides File doctype: `override_doctype_class = {"File": "frappe_vault.overrides.vault_file.VaultFile"}`
- Custom URL renderer: `page_renderer = ["frappe_vault.renderers.vault_file_renderer.VaultFileRenderer"]`
- Serves files at: /vault-file/<id>/
- After delete hook cleans S3/local storage
