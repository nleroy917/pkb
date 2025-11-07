from abc import ABC, abstractmethod
from typing import Iterator, Optional

from pkb.core.models import Document, FileState


class BaseDataSource(ABC):
    """
    Base class for all data sources.

    Data sources are responsible for:
    1. Scanning for files/items in their respective systems
    2. Creating FileState objects for change detection
    3. Extracting content and metadata from items
    4. Converting items to Document objects for indexing
    """

    def __init__(self, source_name: str):
        """
        Initialize data source.

        Args:
            source_name: Unique identifier for this data source (e.g., 'zotero', 'obsidian')
        """
        self.source_name = source_name

    @abstractmethod
    def scan(self) -> Iterator[tuple[str, str]]:
        """
        Scan the data source and yield (file_id, file_path) tuples.

        Returns:
            Iterator of (file_id, file_path) tuples for all items in the source
        """
        raise NotImplementedError

    @abstractmethod
    def create_file_state(self, file_id: str, file_path: str) -> FileState:
        """
        Create a FileState object for a given file.

        Args:
            file_id: Unique identifier for the file
            file_path: Path to the file

        Returns:
            FileState object with hash and metadata
        """
        raise NotImplementedError

    @abstractmethod
    def extract_content(self, file_path: str) -> str:
        """
        Extract text content from a file.

        Args:
            file_path: Path to the file

        Returns:
            Extracted text content
        """
        raise NotImplementedError

    @abstractmethod
    def extract_metadata(self, file_id: str, file_path: str) -> dict:
        """
        Extract metadata for a file.

        Args:
            file_id: Unique identifier for the file
            file_path: Path to the file

        Returns:
            Dictionary of metadata
        """
        raise NotImplementedError

    def create_document(self, file_id: str, file_path: str, content: Optional[str] = None) -> Document:
        """
        Create a Document object from a file.

        Args:
            file_id: Unique identifier for the file
            file_path: Path to the file
            content: Optional pre-extracted content (if None, will extract)

        Returns:
            Document object ready for indexing
        """
        if content is None:
            content = self.extract_content(file_path)

        metadata = self.extract_metadata(file_id, file_path)

        return Document(
            id=file_id,
            source=self.source_name,
            file_path=file_path,
            content=content,
            metadata=metadata,
        )
