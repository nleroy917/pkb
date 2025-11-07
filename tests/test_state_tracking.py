import tempfile
from pathlib import Path

from pkb.core.models import ChangeType, FileState
from pkb.state import ChangeDetector, StateStore, compute_file_hash
from pkb.state.utils import get_file_mtime, get_file_size


def test_state_store_basic():
    """
    Test basic state store operations.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(db_path=Path(tmpdir) / "test.db")

        assert store.get_state_count() == 0

        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Hello, world!")

        state = FileState(
            id="test_id",
            source="test",
            file_path=str(test_file),
            content_hash=compute_file_hash(test_file),
            mtime=get_file_mtime(test_file),
            size=get_file_size(test_file),
        )

        store.save_state(state)
        assert store.get_state_count() == 1

        retrieved = store.get_state("test_id")
        assert retrieved is not None
        assert retrieved.id == "test_id"
        assert retrieved.source == "test"
        assert retrieved.content_hash == state.content_hash

        deleted = store.delete_state("test_id")
        assert deleted is True
        assert store.get_state_count() == 0


def test_change_detector():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(db_path=Path(tmpdir) / "test.db")
        detector = ChangeDetector(store)

        # Create test files
        file1 = Path(tmpdir) / "file1.txt"
        file1.write_text("Content 1")

        file2 = Path(tmpdir) / "file2.txt"
        file2.write_text("Content 2")

        # Create initial states
        state1 = detector.create_file_state(file1, "test", file_id="file1")
        state2 = detector.create_file_state(file2, "test", file_id="file2")

        current_states = {
            "file1": state1,
            "file2": state2,
        }

        # First scan - should detect all as added
        changes = detector.detect_changes(current_states, source="test")
        assert len(changes) == 2
        assert all(c.change_type == ChangeType.ADDED for c in changes)

        # Update state store
        detector.update_stored_states(changes)
        assert store.get_state_count() == 2

        # Second scan with no changes - should detect nothing
        changes = detector.detect_changes(current_states, source="test")
        assert len(changes) == 0

        # Modify file1
        file1.write_text("Modified content 1")
        state1_modified = detector.create_file_state(file1, "test", file_id="file1")
        current_states["file1"] = state1_modified

        # Third scan - should detect file1 as modified
        changes = detector.detect_changes(current_states, source="test")
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.MODIFIED
        assert changes[0].file_state.id == "file1"

        # Update states
        detector.update_stored_states(changes)

        # Remove file2 from current states (simulate deletion)
        del current_states["file2"]

        # Fourth scan - should detect file2 as deleted
        changes = detector.detect_changes(current_states, source="test")
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.DELETED
        assert changes[0].file_state.id == "file2"


def test_changes_summary():
    """Test change summary statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(db_path=Path(tmpdir) / "test.db")
        detector = ChangeDetector(store)

        from pkb.core.models import Change, FileState

        # Create mock changes
        changes = [
            Change(ChangeType.ADDED, FileState("1", "test", "/path/1", "hash1", 0.0, 0)),
            Change(ChangeType.ADDED, FileState("2", "test", "/path/2", "hash2", 0.0, 0)),
            Change(ChangeType.MODIFIED, FileState("3", "test", "/path/3", "hash3", 0.0, 0)),
            Change(ChangeType.DELETED, FileState("4", "test", "/path/4", "hash4", 0.0, 0)),
        ]

        summary = detector.get_changes_summary(changes)
        assert summary["total"] == 4
        assert summary["added"] == 2
        assert summary["modified"] == 1
        assert summary["deleted"] == 1


