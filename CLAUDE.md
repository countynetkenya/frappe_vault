# frappe_vault — Claude Code Context

**Boot:** `../CLAUDE.md` (lean) → `../STATE.md`. Load `../sw/*` per task — **always `../sw/anti-reinvention.md` before building.**
**Skills:** `/frappe-dev` (how-to-implement) for controller/hook work; `/frappe-data-access` for querying vault data. On any conflict, `../sw/` wins.

---

## App Identity

| Key | Value |
|---|---|
| Name | frappe_vault |
| Title | Frappe Vault |
| Version | 0.1.0 |
| Purpose | Secure unified private file serving — presigned S3 URLs for all private files in busara_library |
| Repo | https://github.com/countynetkenya/frappe_vault |
| Staging path | /home/ubuntu/ERPNext/staging/apps/frappe_vault/ |
| Local path | ~/bench-dev/apps/frappe_vault/ (WSL2) |

---

## S3 Configuration

| Key | Value |
|---|---|
| Provider | Hetzner Object Storage |
| Endpoint | fsn1.your-objectstorage.com |
| Bucket | skillwave |
| Region | eu-central-1 |
| Credentials | Stored as `Vault Storage` DocType record (never in code) |

---

## Architecture

### Core Components (all in `frappe_vault/doctype/vault_storage/vault_storage.py`)

```
VaultStorage (frappe.Document)
  — stores connection config: endpoint, bucket_name, access_key, presigned_url_expiry_seconds
  — caches Minio client as cached_property
  — methods: get_download_url(file_key) → presigned URL

VaultFile (extends frappe.core.doctype.file.file.File)
  — registered via: override_doctype_class = {"File": "...VaultFile"}
  — every File doc on a vault-enabled site is a VaultFile instance
  — non-vault files behave identically to core File
  — adds: upload_to_vault(), get_vault_url()

VaultFileRenderer
  — registered via: page_renderer = ["...VaultFileRenderer"]
  — intercepts: GET /vault-file/<id>/<filename>
  — checks session auth + File permissions
  — calls VaultStorage.get_download_url() → 302 redirect to presigned URL
  — presigned URL expiry: configurable per Vault Storage record (default 1800s)

hook_file_after_delete(doc, method)
  — registered via doc_events = {"File": {"after_delete": "..."}}
  — cleans S3/local storage when a File doc is deleted
```

### hooks.py Key Declarations

```python
override_doctype_class = {
    "File": "frappe_vault.frappe_vault.doctype.vault_storage.vault_storage.VaultFile"
}

page_renderer = [
    "frappe_vault.frappe_vault.doctype.vault_storage.vault_storage.VaultFileRenderer"
]

doc_events = {
    "File": {"after_delete": "frappe_vault.frappe_vault.doctype.vault_storage.vault_storage.hook_file_after_delete"}
}

fixtures = [
    {"dt": "Custom Field", "filters": [["dt", "=", "File"], ["fieldname", "in", ["vault_storage", "vault_storage_key"]]]}
]

add_to_apps_screen = [
    {
        "name": "frappe_vault",
        "logo": "/assets/frappe_vault/images/logo.png",  # ← logo.png now exists
        "title": "Frappe Vault",
        "route": "/frappe_vault",
        "has_permission": "frappe_vault.utils.check_app_permission",
    }
]
```

### Workspace

- Workspace JSON: `frappe_vault/frappe_vault/fixtures/Workspace.json` (fixture approach, like busara_library)
- Module Def: "Frappe Vault" (registered in `frappe_vault/frappe_vault/modules.txt`)
- Desk URL: `/app/frappe-vault` → should load after `bench migrate`

---

## File Serving Flow

```
busara_library API endpoint (library_get_read_url)
  → checks Library Book Access Rule
  → calls frappe.get_doc("Vault Storage", name).get_download_url(s3_key)
  → returns presigned URL (15–30 min expiry, never the raw S3 key)

Student browser
  → GET /vault-file/<file_id>/  (or uses presigned URL directly)
  → VaultFileRenderer checks auth → generates presigned URL → 302 redirect
```

**Rule: busara_library must NEVER generate S3 URLs directly. All file access goes through frappe_vault.**

---

## DocType

### Vault Storage
- `title`: display name (e.g. "Skillwave S3")
- `backend`: "S3 Compatible" | "Local"
- `endpoint`: e.g. fsn1.your-objectstorage.com
- `region`, `bucket_name`, `access_key`
- `root_path`: prefix for all objects in bucket
- `presigned_url_expiry_seconds`: default 1800
- `enabled`: 1/0

### Custom Fields on `File` (via fixtures)
- `vault_storage`: Link → Vault Storage (which storage backend holds this file)
- `vault_storage_key`: Data (the object key within the bucket)

---

## Active Bugs / Known Issues

| # | Issue | Status |
|---|---|---|
| 1 | `logo.png` missing → broken app tile icon | ✅ Fixed 2026-06-07 Session 002: hooks.py updated to reference `logo.svg` (file that actually exists in `public/images/`) |
| 2 | `class VaultStorage(frappe.Document)` raises `AttributeError` during `bench migrate` — `frappe.Document` not available at import time during DocType sync | ✅ Fixed 2026-06-07 Session 002: changed to `from frappe.model.document import Document` + `class VaultStorage(Document)` |
| 3 | Workspace not loading — `modules.txt` missing, no workspace JSON | ✅ Fixed 2026-06-07 Session 002: created `modules.txt` + `fixtures/Workspace.json` + hooks.py workspace fixture entry. Confirmed in DB after migrate. |

---

## Utils

`frappe_vault/utils.py`:
```python
def check_app_permission() -> bool:
    return frappe.has_permission("File", throw=False)
```

---

## Never Do

- Generate direct S3 URLs in any controller, template, or API response
- Store S3 credentials in code (use Vault Storage DocType + Frappe password field)
- Modify `apps/frappe/` or `apps/erpnext/`
- Call `frappe.db.commit()` in document lifecycle hooks
