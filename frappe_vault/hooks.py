app_name = "frappe_vault"
app_title = "Frappe Vault"
app_publisher = "County Network Kenya"
app_description = (
    "Secure unified private file serving for Frappe/ERPNext — "
    "local disk and S3-compatible object storage"
)
app_email = "dev@skillwave.ke"
app_license = "MIT"
app_version = "0.1.0"

# ---------------------------------------------------------------------------
# DocType class override – VaultFile replaces the core File controller so
# that every File document gains vault-aware behaviour automatically.
# ---------------------------------------------------------------------------
override_doctype_class = {
    "File": "frappe_vault.frappe_vault.doctype.vault_storage.vault_storage.VaultFile",
}

# ---------------------------------------------------------------------------
# Page renderer – intercepts /vault-file/<id>/<filename> requests.
# Listed BEFORE the default Frappe renderer so we get first pick.
# ---------------------------------------------------------------------------
page_renderer = [
    "frappe_vault.frappe_vault.doctype.vault_storage.vault_storage.VaultFileRenderer",
]

# ---------------------------------------------------------------------------
# Doc events
# ---------------------------------------------------------------------------
doc_events = {
    "File": {
        "after_delete": (
            "frappe_vault.frappe_vault.doctype.vault_storage.vault_storage"
            ".hook_file_after_delete"
        ),
    }
}

# ---------------------------------------------------------------------------
# Fixtures – ship the Custom Fields that attach vault metadata to File docs.
# ---------------------------------------------------------------------------
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "=", "File"],
            ["fieldname", "in", ["vault_storage", "vault_storage_key"]],
        ],
    },
]

# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------
# patches.txt equivalent for Frappe v15/v16 apps (bench migrate picks this up)
# The patch is also idempotent, so re-running is safe.
