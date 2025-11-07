"""
Example usage of enhanced data sources with state tracking.

This demonstrates how to use Zotero and Obsidian data sources
with the state tracking system for change detection.

Generated with AI
"""

from pkb.data_sources import ObsidianDataSource, ZoteroDataSource
from pkb.state import ChangeDetector, StateStore


def example_obsidian_usage():
    """Example: Using Obsidian data source with change detection."""
    print("=== Obsidian Data Source Example ===\n")

    # Initialize data source
    vault_path = "~/Documents/ObsidianVault"
    obsidian = ObsidianDataSource(vault_path)

    print(f"Found {len(obsidian)} markdown files in vault")

    # Initialize state tracking
    state_store = StateStore()  # Uses ~/.pkb/state.db by default
    detector = ChangeDetector(state_store)

    # Scan vault and create file states
    current_states = {}
    for file_id, file_path in obsidian.scan():
        state = obsidian.create_file_state(file_id, file_path)
        current_states[file_id] = state

    # Detect changes
    changes = detector.detect_changes(current_states, source="obsidian")

    # Show summary
    summary = detector.get_changes_summary(changes)
    print("\nChanges detected:")
    print(f"  Added: {summary['added']}")
    print(f"  Modified: {summary['modified']}")
    print(f"  Deleted: {summary['deleted']}")

    # Process changes
    for change in changes:
        print(f"\n{change.change_type.value.upper()}: {change.file_state.file_path}")

        if change.change_type.name in ["ADDED", "MODIFIED"]:
            # Extract content for new/modified files
            content = obsidian.extract_content(change.file_state.file_path)
            print(f"  Content length: {len(content)} chars")

            # Create document for indexing
            doc = obsidian.create_document(
                change.file_state.id, change.file_state.file_path, content=content
            )
            print(f"  Metadata: {doc.metadata.keys()}")

    # Update state store
    detector.update_stored_states(changes)
    print(f"\nState store updated with {len(changes)} changes")


def example_zotero_usage():
    """Example: Using Zotero data source with change detection."""
    print("\n=== Zotero Data Source Example ===\n")

    # Initialize data source (export your Zotero library to CSV first)
    csv_path = "~/Zotero/library.csv"
    zotero = ZoteroDataSource(csv_path)

    print(f"Found {len(zotero)} PDFs in Zotero library")

    # Initialize state tracking
    state_store = StateStore()
    detector = ChangeDetector(state_store)

    # Scan library and create file states
    current_states = {}
    for file_id, file_path in zotero.scan():
        state = zotero.create_file_state(file_id, file_path)
        current_states[file_id] = state

    # Detect changes
    changes = detector.detect_changes(current_states, source="zotero")

    # Show summary
    summary = detector.get_changes_summary(changes)
    print("\nChanges detected:")
    print(f"  Added: {summary['added']}")
    print(f"  Modified: {summary['modified']}")
    print(f"  Deleted: {summary['deleted']}")

    # Process changes
    for change in changes:
        print(
            f"\n{change.change_type.value.upper()}: {change.file_state.metadata.get('title', 'Unknown')}"
        )

        if change.change_type.name in ["ADDED", "MODIFIED"]:
            # Extract PDF content (can be slow for large PDFs)
            # content = zotero.extract_content(change.file_state.file_path)

            # Get metadata without extracting full content
            metadata = zotero.extract_metadata(
                change.file_state.id, change.file_state.file_path
            )
            print(f"  Author: {metadata.get('author', 'N/A')}")
            print(f"  Year: {metadata.get('publication_year', 'N/A')}")
            print(f"  DOI: {metadata.get('doi', 'N/A')}")

    # Update state store
    detector.update_stored_states(changes)
    print(f"\nState store updated with {len(changes)} changes")


def example_combined_workflow():
    """Example: Combined workflow with multiple sources."""
    print("\n=== Combined Workflow Example ===\n")

    # Initialize both data sources
    obsidian = ObsidianDataSource("~/Documents/ObsidianVault")
    zotero = ZoteroDataSource("~/Zotero/library.csv")

    # Single state store for all sources
    state_store = StateStore()
    detector = ChangeDetector(state_store)

    # Process Obsidian
    print("Processing Obsidian vault...")
    obsidian_states = {}
    for file_id, file_path in obsidian.scan():
        obsidian_states[file_id] = obsidian.create_file_state(file_id, file_path)

    obsidian_changes = detector.detect_changes(obsidian_states, source="obsidian")
    print(f"  Obsidian changes: {len(obsidian_changes)}")

    # Process Zotero
    print("Processing Zotero library...")
    zotero_states = {}
    for file_id, file_path in zotero.scan():
        zotero_states[file_id] = zotero.create_file_state(file_id, file_path)

    zotero_changes = detector.detect_changes(zotero_states, source="zotero")
    print(f"  Zotero changes: {len(zotero_changes)}")

    # Update state store
    all_changes = obsidian_changes + zotero_changes
    detector.update_stored_states(all_changes)

    print(f"\nTotal changes: {len(all_changes)}")
    print(f"State store now tracks {state_store.get_state_count()} files")


if __name__ == "__main__":
    # Uncomment the examples you want to run
    # example_obsidian_usage()
    # example_zotero_usage()
    # example_combined_workflow()
    print("Uncomment the example functions to run them with your actual data.")
