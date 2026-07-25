"""
File storage service with support for local, S3, GCS, and MinIO backends.
"""
import logging
import os
from typing import Optional
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class StorageService:
    """
    Service for file storage operations.
    Uses Django's storage backend abstraction for provider flexibility.
    Supports: Local, S3, GCS, MinIO, Azure Blob
    """

    @staticmethod
    def save_file(file_path: str, content: bytes) -> str:
        """
        Save a file to storage.
        Returns the URL/path of the saved file.
        """
        saved_path = default_storage.save(file_path, ContentFile(content))
        logger.info(f"Saved file: {saved_path}")
        return saved_path

    @staticmethod
    def save_uploaded_file(file_path: str, uploaded_file) -> str:
        """
        Save an uploaded file to storage.
        """
        saved_path = default_storage.save(file_path, uploaded_file)
        logger.info(f"Saved uploaded file: {saved_path}")
        return saved_path

    @staticmethod
    def delete_file(file_path: str) -> bool:
        """
        Delete a file from storage.
        """
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
            logger.info(f"Deleted file: {file_path}")
            return True
        return False

    @staticmethod
    def get_file_url(file_path: str) -> str:
        """
        Get the URL for a stored file.
        """
        return default_storage.url(file_path)

    @staticmethod
    def file_exists(file_path: str) -> bool:
        """
        Check if a file exists in storage.
        """
        return default_storage.exists(file_path)

    @staticmethod
    def get_file_size(file_path: str) -> Optional[int]:
        """
        Get the file size in bytes.
        """
        if default_storage.exists(file_path):
            return default_storage.size(file_path)
        return None