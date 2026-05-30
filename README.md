# frappe_vault

[![CI](https://github.com/county-network-kenya/frappe_vault/actions/workflows/ci.yml/badge.svg)](https://github.com/county-network-kenya/frappe_vault/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Frappe v16](https://img.shields.io/badge/Frappe-%3E%3D16.0-blue)](https://frappeframework.com)

**frappe_vault** is an open-source Frappe app that provides secure, unified
private file serving for Frappe/ERPNext sites.  It replaces Frappe's default
file serving with a permission-aware, backend-agnostic approach supporting:

- **Local disk** — streams files from any absolute path with Frappe permission enforcement.
- **S3-compatible object storage** — generates short-lived presigned URLs and
  issues an HTTP 302 redirect, so large files bypass your app server entirely.

---

## Features

| | Local | S3 Compatible |
|---|:---:|:---:|
| Frappe permission check | ✅ | ✅ |
| Streams via app server | ✅ | ❌ (presigned redirect) |
| Works with Frappe Cloud | ✅ | ✅ |
| Auto-deletes on File delete | — | ✅ |
| Bulk import of existing objects | — | ✅ |

---

## Supported S3-compatible providers

| Provider | Endpoint format |
|---|---|
| **Hetzner Object Storage** | `<location>.your-objectstorage.com` |
| **AWS S3** | `s3.amazonaws.com` |
| **MinIO** | `minio.yourdomain.com` |
| **Wasabi** | `s3.wasabisys.com` |
| **DigitalOcean Spaces** | `<region>.digitaloceanspaces.com` |
| **Backblaze B2** | `s3.us-west-004.backblazeb2.com` *(S3-compat mode)* |
| **Cloudflare R2** | `<account>.r2.cloudflarestorage.com` |

Any endpoint that speaks the S3 API (AWS Signature v4) works.

---

## Requirements

- Frappe **≥ 16.0**
- Python **≥ 3.10**
- [`minio`](https://pypi.org/project/minio/) Python package (installed automatically)

---

## Installation

```bash
# 1. Get the app
bench get-app https://github.com/county-network-kenya/frappe_vault

# 2. Install on your site
bench --site <your-site> install-app frappe_vault

# 3. Run migrations (installs Custom Fields on the File DocType)
bench --site <your-site> migrate
```

> **Frappe Cloud**: use the *Apps* tab in your Cloud dashboard to install the
> app from GitHub, then click **Migrate** on your bench.

---

## Configuration

### 1 — Create a Vault Storage document

Go to **Frappe Vault → Vault Storage → New** and fill in:

**S3 Compatible backend:**

| Field | Example |
|---|---|
| Title | `Hetzner-FSN1` |
| Backend | `S3 Compatible` |
| Endpoint | `fsn1.your-objectstorage.com` |
| Region | `eu-central-1` |
| Bucket Name | `my-private-bucket` |
| Access Key | `<your key>` |
| Secret Key | `<your secret>` |
| Presigned URL Expiry (seconds) | `10800` *(3 h)* |

**Local backend:**

| Field | Example |
|---|---|
| Title | `Archive-NAS` |
| Backend | `Local` |
| Root Path | `/mnt/nas/frappe-files` |

### 2 — Attach a vault file

When creating or updating a **File** document, set the two extra fields:

| Field | Value |
|---|---|
| `vault_storage` | Link to your Vault Storage (e.g. `Hetzner-FSN1`) |
| `vault_storage_key` | The S3 object key or local relative path (e.g. `pdfs/report-2024.pdf`) |

Files served via vault use the URL pattern `/vault-file/<file-id>/<filename>`.

### 3 — Bulk-import existing S3 objects

If you already have objects in an S3 bucket and want to register them as
Frappe File documents:

```bash
bench --site <your-site> execute \
    frappe_vault.frappe_vault.utils.register_s3_files.run \
    --kwargs '{
        "vault_storage": "Hetzner-FSN1",
        "prefix": "pdfs/",
        "attached_to_doctype": "Customer",
        "dry_run": true
    }'
```

Remove `"dry_run": true` to actually create the records.

---

## How it works

```
Browser                 Frappe / frappe_vault          Storage
  |                            |                          |
  |-- GET /vault-file/ABC/x -->|                          |
  |                            |-- permission check       |
  |                            |                          |
  |          S3 backend:       |                          |
  |<-- 302 presigned URL ------| <-- presigned URL -------|
  |-- GET presigned URL --------------------------------------------->|
  |<-- file bytes ---------------------------------------------------|
  |                            |                          |
  |          Local backend:    |                          |
  |<-- 200 file bytes ---------| read(path) ------------->|
```

`VaultFile` is registered via `override_doctype_class`, so **every** File
document on your site is vault-aware.  Files that have no `vault_storage_key`
behave identically to core Frappe File documents.

---

## Development

```bash
# Clone
git clone https://github.com/county-network-kenya/frappe_vault
cd frappe_vault

# Lint
pip install ruff
ruff check frappe_vault/
```

Pull requests are welcome!  Please open an issue first for significant changes.

---

## License

[MIT](LICENSE) © 2025 County Network Kenya
