# Changelog

All notable changes to `s3vault` will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2025-01-01

### Added
- **Vault Storage** DocType with S3 Compatible and Local backends.
- **VaultFile** — `override_doctype_class` subclass of the core Frappe `File`
  controller.  Non-vault files are completely transparent.
- **VaultFileRenderer** — `page_renderer` serving `/vault-file/<id>/<filename>`:
  - S3 backend: HTTP 302 redirect to a time-limited presigned URL.
  - Local backend: permission-checked byte-stream from disk.
- **Custom Fields** fixture and patch to attach `vault_storage` (Link) and
  `vault_storage_key` (Data) to the built-in File DocType.
- **`register_s3_files`** utility for bulk-registering existing S3 objects as
  Frappe File documents.
- `doc_events` hook to delete S3 objects when a vault File is deleted.
- MIT License.

[0.1.0]: https://github.com/county-network-kenya/s3vault/releases/tag/v0.1.0
