import hashlib
import os

from pathlib import Path
from typing import BinaryIO


def compute_file_hash(file_path: str | Path, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """
    Compute hash of file content.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm ('md5', 'sha256', etc.)
        chunk_size: Size of chunks to read (for large files)

    Returns:
        Hex digest of file hash
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    hash_obj = hashlib.new(algorithm)

    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def compute_content_hash(content: str | bytes, algorithm: str = "sha256") -> str:
    """
    Compute hash of string or bytes content.

    Args:
        content: Content to hash
        algorithm: Hash algorithm ('md5', 'sha256', etc.)

    Returns:
        Hex digest of content hash
    """
    hash_obj = hashlib.new(algorithm)

    if isinstance(content, str):
        content = content.encode("utf-8")

    hash_obj.update(content)
    return hash_obj.hexdigest()


def get_file_mtime(file_path: str | Path) -> float:
    """
    Get file modification time.

    Args:
        file_path: Path to the file

    Returns:
        Modification time as Unix timestamp
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    return file_path.stat().st_mtime


def get_file_size(file_path: str | Path) -> int:
    """
    Get file size in bytes.

    Args:
        file_path: Path to the file

    Returns:
        File size in bytes
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    return file_path.stat().st_size