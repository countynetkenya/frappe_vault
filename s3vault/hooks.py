app_name = "s3vault"
app_title = "S3 Vault"
app_publisher = "County Network Kenya"
app_description = (
    "Secure unified private file serving for Frappe/ERPNext — "
    "local disk and S3-compatible object storage"
)
app_email = "dev@skillwave.ke"
app_license = "MIT"
app_version = "0.1.0"

required_apps = ["frappe"]

# Desk app-switcher landing page (matches the Vault workspace slug)
app_home = "/desk/vault"

add_to_apps_screen = [
    {
        "name": "s3vault",
        "logo": "/assets/s3vault/images/logo.svg",
        "title": "S3 Vault",
        "route": "/desk/vault",
        "has_permission": "s3vault.utils.check_app_permission",
    }
]

# ---------------------------------------------------------------------------
# DocType class override – VaultFile replaces the core File controller so
# that every File document gains vault-aware behaviour automatically.
# ---------------------------------------------------------------------------
override_doctype_class = {
    "File": "s3vault.vault.doctype.vault_storage.vault_storage.VaultFile",
}

# ---------------------------------------------------------------------------
# Page renderer – intercepts /vault-file/<id>/<filename> requests.
# Listed BEFORE the default Frappe renderer so we get first pick.
# ---------------------------------------------------------------------------
page_renderer = [
    "s3vault.vault.doctype.vault_storage.vault_storage.VaultFileRenderer",
]

# ---------------------------------------------------------------------------
# Doc events
# ---------------------------------------------------------------------------
doc_events = {
    "File": {
        "after_delete": (
            "s3vault.vault.doctype.vault_storage.vault_storage"
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
    # Desk sidebar entry — NOT auto-created from workspace JSONs (S006 gemba)
    {
        "dt": "Workspace Sidebar",
        "filters": [["name", "in", ["Vault"]]],
    },
]

# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------
# patches.txt equivalent for Frappe v15/v16 apps (bench migrate picks this up)
# The patch is also idempotent, so re-running is safe.
