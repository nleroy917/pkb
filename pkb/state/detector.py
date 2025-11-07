from pathlib import Path
from typing import Optional

from pkb.core.models import Change, ChangeType, FileState
from pkb.state.store import StateStore
from pkb.state.utils import compute_file_hash, get_file_mtime, get_file_size


class ChangeDetector:
    """
    Detects changes in files by comparing current state with stored state.
    """

    def __init__(self, state_store: StateStore):
        """
        Initialize change detector.

        Args:
            state_store: State store for persisting file states
        """
        self.state_store = state_store

    def detect_changes(
        self,
        current_states: dict[str, FileState],
        source: Optional[str] = None
    ) -> list[Change]:
        """
        Detect changes by comparing current states with stored states.

        Args:
            current_states: Dictionary mapping file IDs to current FileState objects
            source: Optional source filter to only check specific data source

        Returns:
            List of detected changes
        """
        changes = []

        if source:
            stored_states = {s.id: s for s in self.state_store.get_states_by_source(source)}
        else:
            stored_states = {s.id: s for s in self.state_store.get_all_states()}

        for file_id, current_state in current_states.items():
            if file_id not in stored_states:
                # new file!
                changes.append(Change(
                    change_type=ChangeType.ADDED,
                    file_state=current_state,
                ))
            else:
                stored_state = stored_states[file_id]
                if current_state.has_changed(stored_state):
                    # modified file!
                    changes.append(Change(
                        change_type=ChangeType.MODIFIED,
                        file_state=current_state,
                        previous_state=stored_state,
                    ))

        # finally, check for deleted files
        for file_id, stored_state in stored_states.items():
            if file_id not in current_states:
                # deleted file
                changes.append(Change(
                    change_type=ChangeType.DELETED,
                    file_state=stored_state,
                    previous_state=stored_state,
                ))

        return changes

    def create_file_state(
        self,
        file_path: str | Path,
        source: str,
        file_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        hash_algorithm: str = "sha256",
    ) -> FileState:
        """
        Create a FileState object for a given file.

        Args:
            file_path: Path to the file
            source: Data source name
            file_id: Optional custom file ID (if None, will use hash of source + path)
            metadata: Optional metadata dictionary
            hash_algorithm: Hash algorithm to use

        Returns:
            FileState object
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # generate file ID if not provided
        if file_id is None:
            from pkb.state.utils import compute_content_hash
            file_id = compute_content_hash(f"{source}:{file_path}", algorithm="sha256")

        # compute file hash and metadata
        content_hash = compute_file_hash(file_path, algorithm=hash_algorithm)
        mtime = get_file_mtime(file_path)
        size = get_file_size(file_path)

        return FileState(
            id=file_id,
            source=source,
            file_path=str(file_path.absolute()),
            content_hash=content_hash,
            mtime=mtime,
            size=size,
            metadata=metadata or {},
        )

    def update_stored_states(self, changes: list[Change]) -> None:
        """
        Update state store based on detected changes.

        Args:
            changes: List of changes to apply
        """
        for change in changes:
            if change.change_type == ChangeType.DELETED:
                # remove deleted file from state store
                self.state_store.delete_state(change.file_state.id)
            else:
                # add or update file state
                self.state_store.save_state(change.file_state)

    def is_file_changed(self, file_path: str | Path, source: str) -> bool:
        """
        Quick check if a single file has changed.

        Args:
            file_path: Path to the file
            source: Data source name

        Returns:
            True if file has changed or is new, False otherwise
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return False

        # create current state
        current_state = self.create_file_state(file_path, source)

        # get stored state
        stored_state = self.state_store.get_state(current_state.id)

        if stored_state is None:
            # new file
            return True

        # check if changed
        return current_state.has_changed(stored_state)

    def get_changes_summary(self, changes: list[Change]) -> dict:
        """
        Get summary statistics of changes.

        Args:
            changes: List of changes

        Returns:
            Dictionary with change counts
        """
        summary = {
            "total": len(changes),
            "added": 0,
            "modified": 0,
            "deleted": 0,
        }

        for change in changes:
            if change.change_type == ChangeType.ADDED:
                summary["added"] += 1
            elif change.change_type == ChangeType.MODIFIED:
                summary["modified"] += 1
            elif change.change_type == ChangeType.DELETED:
                summary["deleted"] += 1

        return summary