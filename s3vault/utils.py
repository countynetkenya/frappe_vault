import frappe


def check_app_permission() -> bool:
    """Check if current user has permission to access S3 Vault."""
    return frappe.has_permission("File", throw=False)
