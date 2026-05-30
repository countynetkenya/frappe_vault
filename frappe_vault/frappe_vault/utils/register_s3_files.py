"""
frappe_vault.frappe_vault.utils.register_s3_files
==================================================

Bulk-register existing S3 objects as Frappe File documents linked to a
given Vault Storage backend.

Usage (from bench shell):

    bench --site <site> execute \
        frappe_vault.frappe_vault.utils.register_s3_files.run \
        --kwargs '{
            "vault_storage": "My-S3-Backend",
            "prefix": "busara/library/pdfs/",
            "attached_to_doctype": "Library Document",
            "attached_to_name": null,
            "dry_run": false
        }'

Arguments:
    vault_storage (str):
        Name of the Vault Storage document to use as the backend.
    prefix (str, optional):
        S3 object key prefix to list.  Defaults to "" (all objects).
    attached_to_doctype (str, optional):
        If provided, every created File is linked to this DocType via
        `attached_to_doctype`.  Set `attached_to_name` as well if you want
        to pin to a specific document.
    attached_to_name (str, optional):
        Specific document name within `attached_to_doctype`.
    dry_run (bool):
        If True, list objects and print what *would* be created without
        touching the database.  Defaults to False.

Returns:
    dict with keys:
        - listed:  total objects found in S3
        - skipped: objects that already had a File record
        - created: File records created
        - errors:  list of (object_key, error_message) tuples
"""

from __future__ import annotations

import os

import frappe
from frappe import _
from frappe.utils import now_datetime


def run(
    vault_storage: str,
    prefix: str = "",
    attached_to_doctype: str | None = None,
    attached_to_name: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Register existing S3 objects as Frappe File documents."""

    storage_doc = frappe.get_doc("Vault Storage", vault_storage)

    if storage_doc.backend != "S3 Compatible":
        frappe.throw(_("register_s3_files only supports S3 Compatible backends"))

    if not storage_doc.enabled:
        frappe.throw(_("Vault Storage {0} is disabled").format(vault_storage))

    client = storage_doc.client
    bucket = storage_doc.bucket_name

    result: dict = {
        "listed": 0,
        "skipped": 0,
        "created": 0,
        "errors": [],
    }

    # ---- List objects -------------------------------------------------------
    objects = client.list_objects(bucket, prefix=prefix, recursive=True)

    for obj in objects:
        object_key: str = obj.object_name
        result["listed"] += 1

        # Check for existing File record
        existing = frappe.db.get_value(
            "File",
            {"vault_storage_key": object_key, "vault_storage": vault_storage},
            "name",
        )
        if existing:
            result["skipped"] += 1
            frappe.logger("frappe_vault").debug(
                f"Skipping {object_key!r}: already registered as {existing!r}"
            )
            continue

        filename = os.path.basename(object_key) or object_key

        if dry_run:
            frappe.logger("frappe_vault").info(f"[dry-run] Would create File for {object_key!r}")
            result["created"] += 1
            continue

        try:
            file_doc = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": filename,
                    "file_url": f"/vault-file/{{name}}/{filename}",  # placeholder; set after insert
                    "is_private": 1,
                    "vault_storage": vault_storage,
                    "vault_storage_key": object_key,
                    "attached_to_doctype": attached_to_doctype,
                    "attached_to_name": attached_to_name,
                    "file_size": obj.size or 0,
                    "creation": now_datetime(),
                    "modified": now_datetime(),
                }
            )
            # Bypass Frappe's disk validation for vault files
            file_doc.flags.ignore_file_validate = True
            file_doc.insert(ignore_permissions=True)

            # Update file_url now that we have the doc name
            frappe.db.set_value(
                "File",
                file_doc.name,
                "file_url",
                f"/vault-file/{file_doc.name}/{filename}",
            )

            result["created"] += 1
            frappe.logger("frappe_vault").info(
                f"Created File {file_doc.name!r} for S3 object {object_key!r}"
            )

        except Exception as exc:  # noqa: BLE001
            err_msg = str(exc)
            frappe.logger("frappe_vault").error(
                f"Failed to create File for {object_key!r}: {err_msg}"
            )
            result["errors"].append((object_key, err_msg))

    if not dry_run:
        frappe.db.commit()

    # Summary
    mode = "[DRY-RUN] " if dry_run else ""
    frappe.logger("frappe_vault").info(
        f"{mode}register_s3_files complete: "
        f"listed={result['listed']}, "
        f"skipped={result['skipped']}, "
        f"created={result['created']}, "
        f"errors={len(result['errors'])}"
    )
    return result
