import hashlib
import os
import re

from app.core.config import settings


class StorageService:
    def __init__(self):
        os.makedirs(settings.STORAGE_DIR, exist_ok=True)

    @staticmethod
    def calculate_sha256(file_bytes: bytes) -> str:
        """Calcula el hash SHA-256 para prevenir registros duplicados."""
        return hashlib.sha256(file_bytes).hexdigest()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitiza el nombre del archivo para evitar Path Traversal."""
        clean_name = os.path.basename(filename)
        clean_name = re.sub(r"[^a-zA-Z0-9._-]", "_", clean_name)
        return clean_name.strip()

    def save_file(self, filename: str, file_bytes: bytes) -> str:
        """Guarda f?sicamente el archivo en el directorio local."""
        safe_name = self.sanitize_filename(filename)
        file_hash = self.calculate_sha256(file_bytes)
        stored_name = f"{file_hash[:12]}_{safe_name}"
        filepath = os.path.join(settings.STORAGE_DIR, stored_name)

        with open(filepath, "wb") as f:
            f.write(file_bytes)

        return filepath
