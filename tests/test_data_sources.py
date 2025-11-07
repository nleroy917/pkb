import tempfile
from pathlib import Path

import pytest

from pkb.data_sources import ObsidianDataSource, ZoteroDataSource


def test_obsidian_data_source_basic():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        (vault_path / "note1.md").write_text("# Note 1\n\nThis is note 1.")
        (vault_path / "note2.md").write_text("# Note 2\n\nThis is note 2.")
        subfolder = vault_path / "subfolder"
        subfolder.mkdir()
        (subfolder / "note3.md").write_text("# Note 3\n\nThis is note 3.")

        obsidian_folder = vault_path / ".obsidian"
        obsidian_folder.mkdir()
        (obsidian_folder / "config.md").write_text("Config")

        source = ObsidianDataSource(str(vault_path))

        assert len(source) == 3  # Should not include .obsidian file

        scanned_files = list(source.scan())
        assert len(scanned_files) == 3

        for file_id, file_path in scanned_files:
            assert isinstance(file_id, str)
            assert isinstance(file_path, str)
            assert Path(file_path).exists()

        file_id, file_path = scanned_files[0]
        state = source.create_file_state(file_id, file_path)

        assert state.id == file_id
        assert state.source == "obsidian"
        assert state.file_path == file_path
        assert state.content_hash is not None
        assert state.mtime > 0
        assert state.size > 0

        content = source.extract_content(file_path)
        assert "# Note" in content
        assert len(content) > 0

        metadata = source.extract_metadata(file_id, file_path)
        assert "file_id" in metadata
        assert "relative_path" in metadata
        assert "filename" in metadata

        doc = source.create_document(file_id, file_path)
        assert doc.id == file_id
        assert doc.source == "obsidian"
        assert doc.content is not None
        assert len(doc.metadata) > 0


def test_obsidian_frontmatter():
    """
    Test YAML frontmatter parsing.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # create note with frontmatter
        note_with_frontmatter = vault_path / "note_fm.md"
        note_with_frontmatter.write_text(
            """---
title: Test Note
tags: [test, example]
date: 2024-01-01
---

# Content

This is the content."""
        )

        source = ObsidianDataSource(str(vault_path))
        file_id, file_path = list(source.scan())[0]

        metadata = source.extract_metadata(file_id, file_path)

        if "frontmatter" in metadata:
            fm = metadata["frontmatter"]
            assert "title" in fm or "tags" in fm


def test_obsidian_exclusion_patterns():
    """
    Test exclusion patterns.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # create files in different locations
        (vault_path / "include.md").write_text("Include this")

        templates = vault_path / "templates"
        templates.mkdir()
        (templates / "template.md").write_text("Template")

        obsidian = vault_path / ".obsidian"
        obsidian.mkdir()
        (obsidian / "config.md").write_text("Config")

        source = ObsidianDataSource(str(vault_path))

        # should only include the main file
        scanned = list(source.scan())
        assert len(scanned) == 1

        file_id, file_path = scanned[0]
        assert "include.md" in file_path


def test_obsidian_custom_patterns():
    """
    Test custom include/exclude patterns.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # create various files
        (vault_path / "note.md").write_text("Note")
        (vault_path / "doc.markdown").write_text("Doc")
        (vault_path / "readme.txt").write_text("Readme")

        # custom patterns to include both .md and .markdown
        source = ObsidianDataSource(
            str(vault_path),
            include_patterns=["**/*.md", "**/*.markdown"],
            exclude_patterns=[],
        )

        scanned = list(source.scan())
        assert len(scanned) == 2  # should include .md and .markdown, not .txt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])