"""
s3vault — Vault Storage controller + VaultFile override + VaultFileRenderer.

Design:
  * VaultStorage  – Document subclass; caches a Minio client as a cached_property.
  * VaultFile     – File subclass registered via override_doctype_class. Every
                    File document on a vault-enabled site is an instance of this
                    class.  Non-vault files behave identically to core File.
  * VaultFileRenderer – page_renderer that serves /vault-file/<id>/<filename>.
  * hook_file_after_delete – cleans up S3 objects when a vault File is deleted.
"""

from __future__ import annotations

import os
import re
from datetime import timedelta
from functools import cached_property
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.core.doctype.file.file import File
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password

if TYPE_CHECKING:
    from minio import Minio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_vault_storage(name: str) -> "VaultStorage":
    """Return a cached VaultStorage document (frappe request-level cache)."""
    cache_key = f"vault_storage::{name}"
    doc = frappe.cache().hget("s3vault", cache_key)
    if doc is None:
        doc = frappe.get_doc("Vault Storage", name)
        frappe.cache().hset("s3vault", cache_key, doc)
    return doc


# ---------------------------------------------------------------------------
# VaultStorage Document
# ---------------------------------------------------------------------------

class VaultStorage(Document):
    # Frappe metadata
    # (doctype, module are inferred from the JSON; listed here for IDE support)
    title: str
    backend: str          # "S3 Compatible" | "Local"
    endpoint: str
    region: str
    bucket_name: str
    access_key: str
    root_path: str
    presigned_url_expiry_seconds: int
    enabled: int

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        if self.backend == "S3 Compatible":
            for fld in ("endpoint", "bucket_name", "access_key"):
                if not self.get(fld):
                    frappe.throw(_("Field '{0}' is required for S3 Compatible backend").format(fld))
            # Ensure secret_key exists (Password field – stored encrypted)
            if not get_decrypted_password("Vault Storage", self.name, "secret_key", raise_exception=False):
                frappe.throw(_("Secret Key is required for S3 Compatible backend"))
        elif self.backend == "Local":
            if not self.root_path:
                frappe.throw(_("Root Path is required for Local backend"))
            if not os.path.isabs(self.root_path):
                frappe.throw(_("Root Path must be an absolute filesystem path"))

    # ------------------------------------------------------------------
    # S3 client (lazily initialised, cached per Python object lifetime)
    # ------------------------------------------------------------------

    @cached_property
    def client(self) -> "Minio":
        """Return an initialised Minio client for S3-compatible backends."""
        if self.backend != "S3 Compatible":
            raise RuntimeError("client is only available for S3 Compatible backends")

        try:
            from minio import Minio as _Minio  # noqa: PLC0415
        except ImportError as exc:
            frappe.throw(
                _("The 'minio' Python package is required. Install it with: pip install minio"),
                exc=exc,
            )

        secret = get_decrypted_password("Vault Storage", self.name, "secret_key", raise_exception=True)
        endpoint = self.endpoint.rstrip("/")
        # Strip protocol prefix if someone pastes a full URL
        endpoint = re.sub(r"^https?://", "", endpoint)

        return _Minio(
            endpoint=endpoint,
            access_key=self.access_key,
            secret_key=secret,
            region=self.region or "us-east-1",
            secure=True,
        )

    # ------------------------------------------------------------------
    # Presigned URL generation
    # ------------------------------------------------------------------

    def get_presigned_url(self, object_key: str) -> str:
        """Return a time-limited presigned GET URL for the given S3 object key."""
        if self.backend != "S3 Compatible":
            frappe.throw(_("get_presigned_url() called on a non-S3 Vault Storage"))

        expiry_seconds = self.presigned_url_expiry_seconds or 10800
        url = self.client.presigned_get_object(
            bucket_name=self.bucket_name,
            object_name=object_key,
            expires=timedelta(seconds=expiry_seconds),
        )
        return url

    # ------------------------------------------------------------------
    # Local path resolution
    # ------------------------------------------------------------------

    def resolve_local_path(self, object_key: str) -> str:
        """Resolve an object key to an absolute local filesystem path."""
        if self.backend != "Local":
            frappe.throw(_("resolve_local_path() called on a non-Local Vault Storage"))
        # Prevent path traversal
        safe_key = os.path.normpath(object_key).lstrip("/")
        full_path = os.path.join(self.root_path, safe_key)
        # Ensure resolved path stays inside root_path
        real_root = os.path.realpath(self.root_path)
        real_path = os.path.realpath(full_path)
        if not real_path.startswith(real_root + os.sep) and real_path != real_root:
            frappe.throw(_("Path traversal detected in object key"))
        return real_path


# ---------------------------------------------------------------------------
# VaultFile – File DocType override
# ---------------------------------------------------------------------------

class VaultFile(File):
    """
    Subclasses the core Frappe File controller to add vault-aware behaviour.

    Non-vault files (no vault_storage_key set) are fully transparent —
    all methods delegate to the parent implementation.
    """

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_vault_file(self) -> bool:
        """True when this File is managed by a Vault Storage backend."""
        return bool(self.get("vault_storage_key"))

    @property
    def is_remote_file(self) -> bool:  # type: ignore[override]
        """
        Frappe uses is_remote_file to decide whether to look for a local
        file.  Vault files that live in S3 are remote; local vault files
        are not remote (we stream them ourselves).
        """
        if not self.is_vault_file:
            return super().is_remote_file  # type: ignore[return-value]
        storage = _get_vault_storage(self.vault_storage)
        return storage.backend == "S3 Compatible"

    # ------------------------------------------------------------------
    # Validation overrides (prevent Frappe from rejecting vault files)
    # ------------------------------------------------------------------

    def validate_file_url(self) -> None:  # type: ignore[override]
        # Skip URL validation for vault files: during insert the URL contains a
        # {name} placeholder that is rewritten post-insert, and vault:// paths
        # are not recognised by Frappe's default URL checker.
        if self.is_vault_file:
            return
        super().validate_file_url()

    def validate_file_on_disk(self) -> bool:  # type: ignore[override]
        if self.is_vault_file:
            return True  # Always pass – vault storage is authoritative
        return super().validate_file_on_disk()

    def exists_on_disk(self) -> bool:  # type: ignore[override]
        if self.is_vault_file:
            return False  # We never expect a local Frappe private/files copy
        return super().exists_on_disk()

    # ------------------------------------------------------------------
    # Vault URL generation
    # ------------------------------------------------------------------

    def get_vault_url(self) -> str:
        """
        Return the URL to serve this vault file.

        * S3 backend  → presigned redirect URL (caller should HTTP 302)
        * Local backend → /vault-file/<name>/<filename> internal route
                          (VaultFileRenderer streams the bytes)
        """
        if not self.is_vault_file:
            frappe.throw(_("get_vault_url() called on a non-vault File"))

        storage = _get_vault_storage(self.vault_storage)

        if storage.backend == "S3 Compatible":
            return storage.get_presigned_url(self.vault_storage_key)

        # Local backend: return internal route; renderer will stream
        filename = self.file_name or os.path.basename(self.vault_storage_key)
        return f"/vault-file/{self.name}/{filename}"

    # ------------------------------------------------------------------
    # Download helper
    # ------------------------------------------------------------------

    def is_downloadable(self) -> bool:
        """
        Check whether the currently logged-in user may download this file.
        Delegates to Frappe's own permission model.
        """
        return frappe.has_permission("File", doc=self, ptype="read")


# ---------------------------------------------------------------------------
# VaultFileRenderer – page_renderer
# ---------------------------------------------------------------------------

# Pattern: /vault-file/<file_doc_name>/<original_filename_with_ext>
_VAULT_URL_RE = re.compile(r"^/vault-file/([^/]+)/([^/]+)$")


class VaultFileRenderer:
    """
    Frappe page_renderer that intercepts /vault-file/<id>/<filename> requests.

    Registered in hooks.py under `page_renderer`.  Frappe calls `can_render()`
    first; if it returns True, `render()` is called to produce the response.
    """

    def __init__(self, path: str, status_code: int | None = None) -> None:
        self.path = "/" + path.lstrip("/")
        self.status_code = status_code
        self._match = _VAULT_URL_RE.match(self.path)

    # ------------------------------------------------------------------

    def can_render(self) -> bool:
        return bool(self._match)

    # ------------------------------------------------------------------

    def render(self):  # noqa: ANN201
        import werkzeug.wrappers  # noqa: PLC0415

        file_id = self._match.group(1)

        try:
            file_doc: VaultFile = frappe.get_doc("File", file_id)
        except frappe.DoesNotExistError:
            frappe.throw(_("File not found"), frappe.DoesNotExistError)

        # Permission check
        if not file_doc.is_downloadable():
            frappe.throw(_("You do not have permission to access this file"), frappe.PermissionError)

        if not file_doc.is_vault_file:
            # Not a vault file — fall back to Frappe default behaviour
            frappe.throw(_("This route only serves vault-managed files"), frappe.InvalidRequestArgument)

        storage = _get_vault_storage(file_doc.vault_storage)

        # ---- S3: redirect ---------------------------------------------------
        if storage.backend == "S3 Compatible":
            presigned = storage.get_presigned_url(file_doc.vault_storage_key)
            response = werkzeug.wrappers.Response(status=302)
            response.headers["Location"] = presigned
            response.headers["Cache-Control"] = "no-store"
            return response

        # ---- Local: stream --------------------------------------------------
        local_path = storage.resolve_local_path(file_doc.vault_storage_key)

        if not os.path.isfile(local_path):
            frappe.throw(_("File not found on disk"), frappe.DoesNotExistError)

        import mimetypes  # noqa: PLC0415

        mime_type, _ = mimetypes.guess_type(local_path)
        mime_type = mime_type or "application/octet-stream"

        file_size = os.path.getsize(local_path)
        filename = file_doc.file_name or os.path.basename(local_path)

        def _generate():
            with open(local_path, "rb") as fh:
                while chunk := fh.read(65536):
                    yield chunk

        response = werkzeug.wrappers.Response(
            _generate(),
            status=200,
            mimetype=mime_type,
            direct_passthrough=True,
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["Content-Length"] = str(file_size)
        response.headers["Cache-Control"] = "no-store"
        return response


# ---------------------------------------------------------------------------
# Doc event hook
# ---------------------------------------------------------------------------

def hook_file_after_delete(doc: VaultFile, method: str | None = None) -> None:
    """
    Called after a File document is deleted.
    If the file is a vault S3 file, attempt to remove the object from the bucket.

    Failures are logged as warnings (not raised) to avoid blocking deletions.
    """
    if not getattr(doc, "vault_storage_key", None):
        return
    if not getattr(doc, "vault_storage", None):
        return

    try:
        storage = _get_vault_storage(doc.vault_storage)
        if storage.backend == "S3 Compatible" and storage.enabled:
            storage.client.remove_object(storage.bucket_name, doc.vault_storage_key)
            frappe.logger("s3vault").info(
                f"Deleted S3 object {doc.vault_storage_key!r} from {storage.bucket_name!r}"
            )
    except Exception as exc:  # noqa: BLE001
        frappe.logger("s3vault").warning(
            f"Could not delete S3 object {doc.vault_storage_key!r}: {exc}"
        )
