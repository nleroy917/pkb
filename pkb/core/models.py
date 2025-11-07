from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ChangeType(Enum):
    """Type of change detected in a document."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class FileState:
    """
    Represents the state of a file at a point in time.
    Used for change detection.
    """

    id: str  # unique identifier (e.g., hash of source + file_path)
    source: str  # data source name (e.g., 'zotero', 'obsidian')
    file_path: str  # absolute path to the file
    content_hash: str  # hash of file content (MD5 or SHA256)
    mtime: float  # modification time (Unix timestamp)
    size: int  # file size in bytes
    metadata: dict[str, Any] = field(default_factory=dict)  # Source-specific metadata
    last_indexed: datetime = field(default_factory=datetime.now)

    def __eq__(self, other) -> bool:
        """
        Two FileStates are equal if their content_hash matches.
        """
        if not isinstance(other, FileState):
            return False
        return self.content_hash == other.content_hash

    def has_changed(self, other: "FileState") -> bool:
        """
        Check if file has changed compared to another state.
        """
        return self.content_hash != other.content_hash


@dataclass
class Document:
    """
    Represents a document to be indexed in search backends.
    """

    id: str  # unique document identifier
    source: str  # data source name
    file_path: str  # path to source file
    content: str  # extracted text content
    metadata: dict[str, Any] = field(default_factory=dict)  # Document metadata
    chunks: list[str] = field(default_factory=list)  # Content chunks for embedding
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert document to dictionary for serialization.
        """
        return {
            "id": self.id,
            "source": self.source,
            "file_path": self.file_path,
            "content": self.content,
            "metadata": self.metadata,
            "chunks": self.chunks,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Change:
    """
    Represents a detected change in a document.
    """

    change_type: ChangeType
    file_state: FileState
    previous_state: Optional[FileState] = None

    def __repr__(self) -> str:
        return f"Change({self.change_type.value}, {self.file_state.id})"
