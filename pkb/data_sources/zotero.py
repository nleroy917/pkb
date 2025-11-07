from pathlib import Path
from typing import Iterator

try:
    import polars as pl
except ImportError:
    pl = None

try:
    import pymupdf
except ImportError:
    pymupdf = None

from pkb.core.exceptions import DataSourceException
from pkb.core.models import FileState
from pkb.data_sources.base import BaseDataSource
from pkb.state.utils import (
    compute_content_hash,
    compute_file_hash,
    get_file_mtime,
    get_file_size,
)


class ZoteroDataSource(BaseDataSource):
    """
    Data source for Zotero items.

    Reads from a Zotero CSV export and processes PDF attachments.
    The CSV should be exported from Zotero with "File Attachments" column included.
    """

    def __init__(self, csv_path: str):
        """
        Initialize Zotero data source.

        Args:
            csv_path: Path to Zotero exported CSV file
        """
        super().__init__(source_name="zotero")

        if pl is None:
            raise ImportError(
                "polars is required for ZoteroDataSource. Install with: pip install polars"
            )

        self.csv_path = Path(csv_path)
        if not self.csv_path.exists():
            raise DataSourceException(f"Zotero CSV not found: {csv_path}")

        # load and filter CSV
        self.df_raw = pl.read_csv(self.csv_path)

        # filter for entries with PDF attachments
        self.df_filtered = self._filter_pdfs(self.df_raw)

        # build lookup dict for metadata
        self._metadata_cache = {}
        self._build_metadata_cache()

    def _filter_pdfs(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Filter dataframe for entries with PDF attachments.

        Args:
            df: Input Polars DataFrame

        """
        if "File Attachments" not in df.columns:
            raise DataSourceException(
                "CSV missing 'File Attachments' column. "
                "Export your Zotero library with file attachments included."
            )

        return df.filter(pl.col("File Attachments").str.contains(".pdf")).with_columns(
            pl.col("File Attachments")
            .str.split(";")
            .list.eval(
                pl.element()
                .str.strip_chars()
                .filter(pl.element().str.ends_with(".pdf"))
            )
            .list.first()
            .alias("pdf_file_path")
        )

    def _build_metadata_cache(self):
        """
        Build cache of metadata for each PDF.
        """
        for row in self.df_filtered.iter_rows(named=True):
            pdf_path = row.get("pdf_file_path")
            if not pdf_path:
                continue

            # use absolute path as key
            pdf_path = Path(pdf_path).expanduser().absolute()
            file_id = compute_content_hash(f"{self.source_name}:{pdf_path}")

            self._metadata_cache[str(pdf_path)] = {
                "file_id": file_id,
                "title": row.get("Title", ""),
                "author": row.get("Author", ""),
                "publication_year": row.get("Publication Year", ""),
                "publication_title": row.get("Publication Title", ""),
                "doi": row.get("DOI", ""),
                "url": row.get("Url", ""),
                "abstract": row.get("Abstract Note", ""),
                "tags": row.get("Manual Tags", ""),
                "item_type": row.get("Item Type", ""),
            }

    def scan(self) -> Iterator[tuple[str, str]]:
        """
        Scan Zotero library for PDFs.

        Yields:
            (file_id, file_path) tuples for each PDF
        """
        for pdf_path_str, metadata in self._metadata_cache.items():
            pdf_path = Path(pdf_path_str)
            if not pdf_path.exists():
                continue

            yield metadata["file_id"], str(pdf_path)

    def create_file_state(self, file_id: str, file_path: str) -> FileState:
        """
        Create FileState for a Zotero PDF.

        Args:
            file_id: Unique file identifier
            file_path: Path to PDF file

        Returns:
            FileState object
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        metadata = self._metadata_cache.get(str(file_path.absolute()), {})

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
        Extract text content from PDF.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text content
        """
        if pymupdf is None:
            raise ImportError(
                "pymupdf is required for PDF extraction. Install with: pip install pymupdf"
            )

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        try:
            doc = pymupdf.open(file_path)
            text_parts = []

            for page in doc:
                text_parts.append(page.get_text())

            doc.close()
            return "\n\n".join(text_parts)
        except Exception as e:
            raise DataSourceException(f"Failed to extract PDF content: {e}")

    def extract_metadata(self, file_id: str, file_path: str) -> dict:
        """
        Extract metadata for a Zotero PDF.

        Args:
            file_id: Unique file identifier
            file_path: Path to PDF file

        Returns:
            Dictionary of metadata
        """
        file_path = Path(file_path).absolute()
        return self._metadata_cache.get(str(file_path), {})

    def __len__(self) -> int:
        """
        Return number of PDFs in the library.
        """
        return len(self._metadata_cache)

    def __repr__(self) -> str:
        return f"ZoteroDataSource(csv_path={self.csv_path}, num_pdfs={len(self)})"
