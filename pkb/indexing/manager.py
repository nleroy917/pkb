from typing import Optional

from pkb.core.models import ChangeType, Document
from pkb.data_sources.base import BaseDataSource
from pkb.indexing.processor import DocumentProcessor
from pkb.state import ChangeDetector, StateStore


class IndexManager:
    """
    Orchestrates the indexing workflow:
    1. Scans data sources for files
    2. Detects changes (added/modified/deleted)
    3. Extracts content and metadata
    4. Processes documents (chunking, etc.)
    5. Updates state tracking
    """

    def __init__(
        self,
        state_store_path: Optional[str] = None,
        processor: Optional[DocumentProcessor] = None,
    ):
        """
        Initialize index manager.

        Args:
            state_store_path: Path to state database (default: ~/.pkb/state.db)
            processor: Document processor for chunking (default: creates one with defaults)
        """
        if state_store_path:
            self.state_store = StateStore(state_store_path)
        else:
            self.state_store = StateStore()

        self.detector = ChangeDetector(self.state_store)

        self.processor = processor or DocumentProcessor()

    def index_source(
        self,
        data_source: BaseDataSource,
        process_documents: bool = True,
    ) -> dict:
        """
        Index a data source and return results.

        Args:
            data_source: Data source to index
            process_documents: Whether to process documents (chunking, etc.)

        Returns:
            Dictionary with indexing results:
            {
                'changes': list[Change],
                'documents': dict[str, Document],  # Only for added/modified
                'summary': dict with counts
            }
        """
        print(f"Indexing {data_source.source_name}...")

        # step 1: scan data source and create file states
        print("  Scanning files...")
        current_states = {}
        scan_count = 0

        for file_id, file_path in data_source.scan():
            scan_count += 1
            if scan_count % 10 == 0:
                print(f"    Scanned {scan_count} files...", end="\r")

            try:
                state = data_source.create_file_state(file_id, file_path)
                current_states[file_id] = state
            except Exception as e:
                print(f"  Warning: Failed to create state for {file_path}: {e}")
                continue

        if scan_count > 0:
            print(f"    Scanned {scan_count} files total")
        print(f"  Found {len(current_states)} files")

        # step 2: detect changes
        print("  Detecting changes...")
        changes = self.detector.detect_changes(
            current_states, source=data_source.source_name
        )

        summary = self.detector.get_changes_summary(changes)
        print(
            f"  Changes: {summary['added']} added, {summary['modified']} modified, {summary['deleted']} deleted"
        )

        # step 3: extract content and create documents for added/modified files
        documents = {}

        if process_documents:
            print("  Processing documents...")
            process_count = 0

            for change in changes:
                process_count += 1
                if process_count % 10 == 0:
                    print(f"    Processed {process_count} documents...", end="\r")

                if change.change_type in [ChangeType.ADDED, ChangeType.MODIFIED]:
                    try:
                        # extract content
                        content = data_source.extract_content(
                            change.file_state.file_path
                        )

                        # create document
                        doc = data_source.create_document(
                            change.file_state.id,
                            change.file_state.file_path,
                            content=content,
                        )

                        # process document (chunking)
                        doc = self.processor.process_document(doc)

                        documents[change.file_state.id] = doc

                    except Exception as e:
                        print(
                            f"  Warning: Failed to process {change.file_state.file_path}: {e}"
                        )
                        continue

            print(f"  Processed {len(documents)} documents")

        # step 4: update state store
        print("  Updating state store...")
        self.detector.update_stored_states(changes)

        return {
            "changes": changes,
            "documents": documents,
            "summary": summary,
        }

    def get_status(self, source: Optional[str] = None) -> dict:
        """
        Get indexing status for a source or all sources.

        Args:
            source: Optional source name to filter by

        Returns:
            Dictionary with status information
        """
        if source:
            count = self.state_store.get_state_count(source)
            states = self.state_store.get_states_by_source(source)

            return {
                "source": source,
                "total_files": count,
                "states": states,
            }
        else:
            all_states = self.state_store.get_all_states()
            sources = {}

            for state in all_states:
                if state.source not in sources:
                    sources[state.source] = 0
                sources[state.source] += 1

            return {
                "total_files": len(all_states),
                "sources": sources,
            }

    def clear_source(self, source: str) -> int:
        """
        Clear state for a specific source.

        Args:
            source: Source name to clear

        Returns:
            Number of states deleted
        """
        count = self.state_store.delete_states_by_source(source)
        print(f"Cleared {count} states for source '{source}'")
        return count

    def clear_all(self) -> None:
        """Clear all state tracking data."""
        self.state_store.clear()
        print("Cleared all state tracking data")

    def reindex_source(
        self,
        data_source: BaseDataSource,
        process_documents: bool = True,
    ) -> dict:
        """
        Force a full reindex of a source (clears existing state first).

        Args:
            data_source: Data source to reindex
            process_documents: Whether to process documents

        Returns:
            Dictionary with indexing results
        """
        print(f"Reindexing {data_source.source_name} (clearing old state)...")
        self.clear_source(data_source.source_name)

        return self.index_source(data_source, process_documents=process_documents)

    def get_documents_to_index(
        self,
        data_source: BaseDataSource,
        force: bool = False,
    ) -> list[Document]:
        """
        Get list of documents that need to be indexed.

        Args:
            data_source: Data source to check
            force: If True, return all documents (force reindex)

        Returns:
            List of documents that need indexing
        """
        if force:
            # return all documents
            documents = []
            scan_count = 0
            for file_id, file_path in data_source.scan():
                scan_count += 1
                if scan_count % 10 == 0:
                    print(f"  Scanned {scan_count} files...", end="\r")

                try:
                    doc = data_source.create_document(file_id, file_path)
                    doc = self.processor.process_document(doc)
                    documents.append(doc)
                except Exception as e:
                    print(f"Warning: Failed to create document for {file_path}: {e}")
                    continue

            if scan_count > 0:
                print(f"  Scanned {scan_count} files total")

            return documents
        else:
            # only return changed documents
            result = self.index_source(data_source, process_documents=True)
            return list(result["documents"].values())

    def __repr__(self) -> str:
        status = self.get_status()
        return f"IndexManager(total_files={status['total_files']}, sources={list(status['sources'].keys())})"
