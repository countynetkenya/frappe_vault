"""
Patch: Install Custom Fields that attach vault metadata to the File DocType.

This patch is idempotent — running it multiple times has no effect.

Frappe reads patches.txt in the app root and runs each line once per site,
tracking execution in `__PatchLog`.  Safe to re-run via:

    bench --site <site> run-patch \
        frappe_vault.frappe_vault.patches.v0_1.register_custom_fields.execute
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


# ---------------------------------------------------------------------------
# Custom field definitions
# ---------------------------------------------------------------------------

CUSTOM_FIELDS = {
    "File": [
        {
            "fieldname": "vault_storage",
            "label": "Vault Storage",
            "fieldtype": "Link",
            "options": "Vault Storage",
            "insert_after": "content_hash",
            "no_copy": 1,
            "read_only": 0,
        },
        {
            "fieldname": "vault_storage_key",
            "label": "Vault Storage Key",
            "fieldtype": "Data",
            "insert_after": "vault_storage",
            "no_copy": 1,
            "read_only": 0,
            "description": (
                "S3 object key or local relative path managed by the linked Vault Storage"
            ),
        },
    ]
}


def execute() -> None:
    """Entry point called by bench migrate / run-patch."""
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
    frappe.db.commit()
