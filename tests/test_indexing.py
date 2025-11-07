import tempfile
from pathlib import Path

import pytest

from pkb.core.models import ChangeType, Document
from pkb.data_sources import ObsidianDataSource
from pkb.indexing import DocumentProcessor, IndexManager


def test_document_processor_basic():
    """
    Test basic document chunking.
    """
    processor = DocumentProcessor(chunk_size=100, chunk_overlap=20, min_chunk_size=50)

    # short text (should not be chunked)
    short_text = "This is a short text."
    doc = Document(
        id="test1",
        source="test",
        file_path="/test/path",
        content=short_text,
    )

    processed = processor.process_document(doc)
    assert len(processed.chunks) == 1
    assert processed.chunks[0] == short_text

    # long text (should be chunked)
    long_text = "This is a sentence. " * 20  # ~400 chars
    doc = Document(
        id="test2",
        source="test",
        file_path="/test/path",
        content=long_text,
    )

    processed = processor.process_document(doc)
    assert len(processed.chunks) > 1
    assert all(len(chunk) <= 120 for chunk in processed.chunks)  # chunk_size + some tolerance


def test_document_processor_sentence_boundaries():
    """
    Test that chunking respects sentence boundaries.
    """
    processor = DocumentProcessor(chunk_size=80, chunk_overlap=10, min_chunk_size=30)

    # Create text long enough to need chunking
    sentences = ["This is sentence number one. ", "This is sentence number two. ",
                 "This is sentence number three. ", "This is sentence number four. ",
                 "This is sentence number five. "]
    text = "".join(sentences * 3)  # Repeat to make it long enough

    chunks = processor.chunk_text(text)

    # should create multiple chunks
    assert len(chunks) > 1
    # Most chunks should end at sentence boundaries (with period)
    chunks_ending_with_period = sum(1 for chunk in chunks if chunk.rstrip().endswith("."))
    assert chunks_ending_with_period >= len(chunks) // 2  # At least half should end with period


def test_document_processor_empty_text():
    """
    Test processor with empty text.
    """
    processor = DocumentProcessor()

    doc = Document(
        id="test",
        source="test",
        file_path="/test/path",
        content="",
    )

    processed = processor.process_document(doc)
    assert processed.chunks == []


def test_index_manager_basic():
    """
    Test basic IndexManager functionality.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # create test vault
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()

        (vault_path / "note1.md").write_text("# Note 1\n\nContent for note 1.")
        (vault_path / "note2.md").write_text("# Note 2\n\nContent for note 2.")

        # create data source
        source = ObsidianDataSource(str(vault_path))

        # create index manager with temp state store
        state_db = Path(tmpdir) / "state.db"
        manager = IndexManager(state_store_path=str(state_db))

        # first index - should detect all files as added
        result = manager.index_source(source, process_documents=True)

        assert result["summary"]["added"] == 2
        assert result["summary"]["modified"] == 0
        assert result["summary"]["deleted"] == 0
        assert len(result["documents"]) == 2

        # check documents are processed
        for doc in result["documents"].values():
            assert isinstance(doc, Document)
            assert doc.content is not None
            assert len(doc.chunks) > 0

        # second index - no changes
        result = manager.index_source(source, process_documents=True)

        assert result["summary"]["added"] == 0
        assert result["summary"]["modified"] == 0
        assert result["summary"]["deleted"] == 0
        assert len(result["documents"]) == 0


def test_index_manager_detect_modifications():
    """
    Test that IndexManager detects modified files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()

        note_path = vault_path / "note.md"
        note_path.write_text("Original content")

        source = ObsidianDataSource(str(vault_path))
        state_db = Path(tmpdir) / "state.db"
        manager = IndexManager(state_store_path=str(state_db))

        result = manager.index_source(source)
        assert result["summary"]["added"] == 1

        note_path.write_text("Modified content")

        # second index - should detect modification
        result = manager.index_source(source)
        assert result["summary"]["modified"] == 1
        assert result["summary"]["added"] == 0


def test_index_manager_detect_deletions():
    """
    Test that IndexManager detects deleted files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()

        note1 = vault_path / "note1.md"
        note2 = vault_path / "note2.md"
        note1.write_text("Note 1")
        note2.write_text("Note 2")

        source = ObsidianDataSource(str(vault_path))
        state_db = Path(tmpdir) / "state.db"
        manager = IndexManager(state_store_path=str(state_db))

        result = manager.index_source(source)
        assert result["summary"]["added"] == 2

        note1.unlink()

        # second index - should detect deletion
        result = manager.index_source(source)
        assert result["summary"]["deleted"] == 1
        assert result["summary"]["added"] == 0


def test_index_manager_status():
    """
    Test IndexManager status reporting.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()

        (vault_path / "note.md").write_text("Content")

        source = ObsidianDataSource(str(vault_path))
        state_db = Path(tmpdir) / "state.db"
        manager = IndexManager(state_store_path=str(state_db))
        manager.index_source(source)

        # check status
        status = manager.get_status()
        assert status["total_files"] == 1
        assert "obsidian" in status["sources"]
        assert status["sources"]["obsidian"] == 1

        # check source-specific status
        source_status = manager.get_status(source="obsidian")
        assert source_status["total_files"] == 1
        assert source_status["source"] == "obsidian"


def test_index_manager_clear_source():
    """
    Test clearing state for a specific source.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()

        (vault_path / "note.md").write_text("Content")

        source = ObsidianDataSource(str(vault_path))
        state_db = Path(tmpdir) / "state.db"
        manager = IndexManager(state_store_path=str(state_db))
        manager.index_source(source)
        assert manager.get_status()["total_files"] == 1

        # clear source
        count = manager.clear_source("obsidian")
        assert count == 1
        assert manager.get_status()["total_files"] == 0


def test_index_manager_reindex():
    """
    Test force reindexing.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()

        (vault_path / "note.md").write_text("Content")

        source = ObsidianDataSource(str(vault_path))
        state_db = Path(tmpdir) / "state.db"
        manager = IndexManager(state_store_path=str(state_db))

        # first index
        result = manager.index_source(source)
        assert result["summary"]["added"] == 1

        # reindex (should clear and re-add)
        result = manager.reindex_source(source)
        assert result["summary"]["added"] == 1
        assert result["summary"]["modified"] == 0


def test_index_manager_custom_processor():
    """
    Test IndexManager with custom document processor.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        vault_path.mkdir()

        # create a longer note
        long_content = "This is a sentence. " * 50
        (vault_path / "note.md").write_text(long_content)

        source = ObsidianDataSource(str(vault_path))
        state_db = Path(tmpdir) / "state.db"

        # custom processor with small chunks
        processor = DocumentProcessor(chunk_size=50, chunk_overlap=10)
        manager = IndexManager(state_store_path=str(state_db), processor=processor)

        # index
        result = manager.index_source(source, process_documents=True)

        # check that document was chunked
        doc = list(result["documents"].values())[0]
        assert len(doc.chunks) > 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])