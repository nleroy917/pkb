from pkb.core.models import Document

class DocumentProcessor:
    """
    Processes documents for indexing by:
    1. Chunking large documents into smaller pieces
    2. Generating embeddings (optional, can be done by backends too)
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        """
        Initialize document processor.

        Args:
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum size for a chunk (smaller chunks are merged)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def process_document(self, document: Document) -> Document:
        """
        Process a document by chunking its content.

        Args:
            document: Document to process

        Returns:
            Processed document with chunks populated
        """
        chunks = self.chunk_text(document.content)
        document.chunks = chunks

        return document

    def chunk_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if not text or len(text) <= self.chunk_size:
            return [text] if text else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            if end < len(text):
                sentence_end = self._find_sentence_boundary(text, end - 100, end)
                if sentence_end != -1:
                    end = sentence_end + 1
                else:
                    word_end = self._find_word_boundary(text, end - 50, end)
                    if word_end != -1:
                        end = word_end

            # extract chunk
            chunk = text[start:end].strip()

            # only add chunk if it meets minimum size
            if len(chunk) >= self.min_chunk_size:
                chunks.append(chunk)

            # move start position with overlap
            # ensure we always make progress to avoid infinite loop
            next_start = end - self.chunk_overlap
            if next_start <= start:
                # if overlap would cause us to not progress, just move forward
                start = end if end > start else start + 1
            else:
                start = next_start

        return chunks

    def _find_sentence_boundary(self, text: str, start: int, end: int) -> int:
        """
        Find the last sentence boundary in the given range.
        """
        search_text = text[max(0, start):end]

        for delimiter in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
            pos = search_text.rfind(delimiter)
            if pos != -1:
                return start + pos + len(delimiter) - 1

        return -1

    def _find_word_boundary(self, text: str, start: int, end: int) -> int:
        """
        Find the last word boundary in the given range.
        """
        search_text = text[max(0, start):end]

        for delimiter in [" ", "\n", "\t"]:
            pos = search_text.rfind(delimiter)
            if pos != -1:
                return start + pos

        return -1

    def merge_small_chunks(self, chunks: list[str]) -> list[str]:
        """
        Merge consecutive small chunks together.

        Args:
            chunks: List of chunks to process

        Returns:
            List of merged chunks
        """
        if not chunks:
            return []

        merged = []
        current_chunk = chunks[0]

        for next_chunk in chunks[1:]:
            if len(current_chunk) < self.min_chunk_size:
                # merge with next chunk
                current_chunk = current_chunk + " " + next_chunk
            else:
                # add current chunk and start new one
                merged.append(current_chunk)
                current_chunk = next_chunk

        # add the last chunk
        if current_chunk:
            merged.append(current_chunk)

        return merged

    def __repr__(self) -> str:
        return (
            f"DocumentProcessor(chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}, "
            f"min_chunk_size={self.min_chunk_size})"
        )