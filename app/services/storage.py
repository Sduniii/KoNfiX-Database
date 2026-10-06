import hashlib
import os
import re
from pathlib import Path
from typing import Tuple
from app.config import settings


def sanitize_filename(filename: str | None) -> str:
    """
    Sanitizes untrusted filenames to prevent directory traversal and filesystem attacks.
    Ensures safe characters, resolves separators cross-platform, and enforces .knxprod extension.
    """
    if not filename:
        return "unnamed.knxprod"
    # Normalize Windows/Unix path separators
    cleaned = filename.replace("\\", "/").strip()
    # Strip any directory path components
    cleaned = cleaned.split("/")[-1].strip()
    # Remove null bytes and control characters
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)
    # Remove any traversal patterns
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "")
    # Restrict characters to safe alphanumeric, dashes, underscores, and dots
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", cleaned).strip("._ ")
    if not cleaned:
        cleaned = "unnamed"
    lower_c = cleaned.lower()
    if not (lower_c.endswith(".yaml") or lower_c.endswith(".yml") or lower_c.endswith(".knxprod") or lower_c.endswith(".zip")):
        cleaned += ".knxprod"
    return cleaned


class StorageService:
    def __init__(self, base_dir: str = settings.STORAGE_DIR):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_knxprod_bytes(self, content: bytes, filename: str | None = None) -> Tuple[str, str, int]:
        """
        Saves raw bytes to the catalog storage directory.
        Returns (relative_or_abs_path, sha256_hash, file_size_bytes).
        """
        sha256 = hashlib.sha256(content).hexdigest()
        file_size = len(content)

        clean_name = sanitize_filename(filename) if filename else f"{sha256[:12]}.yaml"

        # Safe filename prefixed with hash prefix to avoid collision
        stored_filename = f"{sha256[:12]}_{clean_name}"
        dest_path = (self.base_dir / stored_filename).resolve()

        # Security check: Ensure target path is strictly within base_dir
        if not dest_path.is_relative_to(self.base_dir):
            raise ValueError("Ungültiger Zielpfad: Dateisystem-Traversal verhindert")

        # Write or overwrite if same hash
        with open(dest_path, "wb") as f:
            f.write(content)

        return str(dest_path), sha256, file_size

    def save_yaml_content(self, yaml_content: str, filename: str | None = None) -> Tuple[str, str, int]:
        """
        Saves a KoNfiX-YAML string to disk as UTF-8 encoded file.
        """
        content_bytes = yaml_content.encode("utf-8")
        clean_name = filename or "device.yaml"
        if not (clean_name.lower().endswith(".yaml") or clean_name.lower().endswith(".yml")):
            clean_name += ".yaml"
        return self.save_knxprod_bytes(content_bytes, clean_name)

    def get_file_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = self.base_dir / p
        resolved = p.resolve()
        if not resolved.is_relative_to(self.base_dir):
            raise ValueError("Zugriff verweigert: Pfad liegt außerhalb des zulässigen Verzeichnisses")
        return resolved

storage_service = StorageService()


