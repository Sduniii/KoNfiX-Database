import os
import hashlib
from pathlib import Path
from typing import Tuple
from app.config import settings

class StorageService:
    def __init__(self, base_dir: str = settings.STORAGE_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_knxprod_bytes(self, content: bytes, filename: str | None = None) -> Tuple[str, str, int]:
        """
        Saves raw bytes to the catalog storage directory.
        Returns (relative_or_abs_path, sha256_hash, file_size_bytes).
        """
        sha256 = hashlib.sha256(content).hexdigest()
        file_size = len(content)

        clean_name = os.path.basename(filename) if filename else f"{sha256[:12]}.knxprod"
        if not clean_name.lower().endswith(".knxprod"):
            clean_name += ".knxprod"

        # Safe filename prefixed with hash prefix to avoid collision
        stored_filename = f"{sha256[:12]}_{clean_name}"
        dest_path = self.base_dir / stored_filename

        # Write or overwrite if same hash
        with open(dest_path, "wb") as f:
            f.write(content)

        return str(dest_path), sha256, file_size

    def get_file_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = self.base_dir / p
        return p

storage_service = StorageService()
