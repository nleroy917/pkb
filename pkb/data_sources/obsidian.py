from pathlib import Path
from typing import Iterator, Optional

from pkb.core.exceptions import DataSourceException
from pkb.core.models import FileState
from pkb.data_sources.base import BaseDataSource
from pkb.state.utils import (
    compute_content_hash,
    compute_file_hash,
    get_file_mtime,
    get_file_size,
)


class ObsidianDataSource(BaseDataSource):
    """
    Data source for Obsidian vault.

    Scans an Obsidian vault directory for markdown files and processes their content.
    """

    def __init__(
        self,
        vault_path: str,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """
        Initialize Obsidian data source.

        Args:
            vault_path: Path to Obsidian vault directory
            include_patterns: Optional list of glob patterns to include (e.g., ['*.md', '**/*.markdown'])
            exclude_patterns: Optional list of glob patterns to exclude (e.g., ['.obsidian/**', 'templates/**'])
        """
        super().__init__(source_name="obsidian")

        self.vault_path = Path(vault_path).expanduser().absolute()

        if not self.vault_path.exists():
            raise DataSourceException(f"Obsidian vault not found: {vault_path}")

        if not self.vault_path.is_dir():
            raise DataSourceException(
                f"Obsidian vault path is not a directory: {vault_path}"
            )

        self.include_patterns = include_patterns or ["**/*.md", "**/*.markdown"]

        # default exclusions: .obsidian folder, .trash, and common template folders
        self.exclude_patterns = exclude_patterns or [
            ".obsidian/**",
            ".trash/**",
            "templates/**",
            "Templates/**",
        ]

    def _should_include(self, file_path: Path) -> bool:
        """
        Check if file should be included based on patterns.
        """
        for pattern in self.exclude_patterns:
            if file_path.match(pattern):
                return False

        for pattern in self.include_patterns:
            if file_path.match(pattern):
                return True

        return False

    def _get_all_files(self) -> list[Path]:
        """
        Get all markdown files in vault matching patterns.
        """
        all_files = []

        for pattern in self.include_patterns:
            matching_files = self.vault_path.glob(pattern)
            for file_path in matching_files:
                if file_path.is_file() and self._should_include(file_path):
                    all_files.append(file_path)

        return all_files

    def scan(self) -> Iterator[tuple[str, str]]:
        """
        Scan Obsidian vault for markdown files.

        Yields:
            (file_id, file_path) tuples for each markdown file
        """
        for file_path in self._get_all_files():
            # generate file ID from source and relative path
            relative_path = file_path.relative_to(self.vault_path)
            file_id = compute_content_hash(f"{self.source_name}:{relative_path}")

            yield file_id, str(file_path)

    def create_file_state(self, file_id: str, file_path: str) -> FileState:
        """
        Create FileState for an Obsidian markdown file.

        Args:
            file_id: Unique file identifier
            file_path: Path to markdown file

        Returns:
            FileState object
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {file_path}")

        relative_path = file_path.relative_to(self.vault_path)

        metadata = {
            "file_id": file_id,
            "relative_path": str(relative_path),
            "filename": file_path.name,
            "folder": str(relative_path.parent)
            if relative_path.parent != Path(".")
            else "",
        }

        return FileState(
            id=file_id,
            source=self.source_name,
            file_path=str(file_path.absolute()),
            content_hash=compute_file_hash(file_path),
            mtime=get_file_mtime(file_path),
            size=get_file_size(file_path),
            metadata=metadata,
        )

    def extract_content(self, file_path: str) -> str:
        """
        Extract text content from markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            Raw markdown content
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise DataSourceException(f"Failed to read markdown file: {e}")

    def extract_metadata(self, file_id: str, file_path: str) -> dict:
        """
        Extract metadata from markdown file.

        Parses YAML frontmatter if present and adds file metadata.

        Args:
            file_id: Unique file identifier
            file_path: Path to markdown file

        Returns:
            Dictionary of metadata
        """
        file_path = Path(file_path)
        relative_path = file_path.relative_to(self.vault_path)

        metadata = {
            "file_id": file_id,
            "relative_path": str(relative_path),
            "filename": file_path.name,
            "folder": str(relative_path.parent)
            if relative_path.parent != Path(".")
            else "",
        }

        try:
            content = self.extract_content(str(file_path))
            frontmatter = self._parse_frontmatter(content)
            if frontmatter:
                metadata["frontmatter"] = frontmatter
        except Exception:
            pass

        return metadata

    def _parse_frontmatter(self, content: str) -> Optional[dict]:
        """
        Parse YAML frontmatter from markdown content.

        Args:
            content: Markdown content

        Returns:
            Dictionary of frontmatter fields, or None if no frontmatter
        """
        if not content.startswith("---\n"):
            return None

        try:
            # find end of frontmatter
            end_idx = content.find("\n---\n", 4)
            if end_idx == -1:
                return None

            frontmatter_text = content[4:end_idx]

            # try to parse YAML (if pyyaml available)
            try:
                import yaml

                return yaml.safe_load(frontmatter_text)
            except ImportError:
                # if yaml not available, do basic parsing
                frontmatter = {}
                for line in frontmatter_text.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        frontmatter[key.strip()] = value.strip()
                return frontmatter
        except Exception:
            return None

    def __len__(self) -> int:
        """
        Return number of markdown files in vault.
        """
        return len(self._get_all_files())

    def __repr__(self) -> str:
        return (
            f"ObsidianDataSource(vault_path={self.vault_path}, num_files={len(self)})"
        )
