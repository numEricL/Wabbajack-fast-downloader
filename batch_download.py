import argparse
import json
import os
import webbrowser

import extract_modlist


DEFAULT_MAX_SIZE_MB = 10
DEFAULT_BATCH_SIZE = 20

def read_links(file_path):
    """Yield non-empty links from a text file."""
    try:
        with open(file_path, 'r') as file:
            for line in file:
                link = line.strip()
                if link:
                    yield link
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")

def read_links_in_batches(file_path, batch_size):
    """Read links from a text file in batches and yield each batch."""
    batch = []
    for link in read_links(file_path):
        batch.append(link)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

def count_lines(file_path):
    """Count the total number of non-empty links in the file."""
    return sum(1 for _ in read_links(file_path))

def load_archive_sizes(modlist_path):
    """Return a mapping of generated Nexus URLs to archive sizes in bytes."""
    try:
        with open(modlist_path, 'r') as file:
            archives = json.load(file).get("Archives", [])
    except FileNotFoundError:
        print(f"Error: The modlist file {modlist_path} was not found.")
        return None
    except json.JSONDecodeError as error:
        print(f"Error: Failed to decode {modlist_path}: {error}")
        return None

    return archive_sizes_from_archives(archives)

def archive_sizes_from_archives(archives):
    """Return a mapping of generated Nexus URLs to archive sizes in bytes."""
    sizes = {}
    for archive in archives:
        state = archive.get("State") if isinstance(archive, dict) else None
        if not isinstance(state, dict) or not {"GameName", "ModID", "FileID"} <= state.keys():
            continue
        url = extract_modlist.generate_url(archive)
        size = archive.get("Size")
        if url and isinstance(size, int) and size >= 0:
            sizes[url] = size
    return sizes

def filter_links_by_size(links, archive_sizes, max_size_mb):
    """Return links within the size limit and URLs skipped for exceeding it."""
    missing_sizes = [link for link in links if link not in archive_sizes]
    if missing_sizes:
        print("Error: Could not find size metadata for every URL in output.txt.")
        return None, []

    max_size_bytes = max_size_mb * 1024 * 1024
    allowed_links = []
    skipped_links = []
    for link in links:
        if archive_sizes[link] > max_size_bytes:
            skipped_links.append(link)
        else:
            allowed_links.append(link)
    return allowed_links, skipped_links

def write_skipped_links(file_path, links):
    """Write skipped URLs to a file, replacing the previous run's log."""
    with open(file_path, 'w') as file:
        file.write('\n'.join(links))
        if links:
            file.write('\n')

def append_skipped_links(file_path, links):
    """Append skipped URLs to a file."""
    if not links:
        return
    with open(file_path, 'a') as file:
        file.write('\n'.join(links))
        file.write('\n')

def append_new_links(file_path, links):
    """Append URLs that are not already present in a log file."""
    existing_links = set(read_links(file_path)) if os.path.exists(file_path) else set()
    new_links = [link for link in links if link not in existing_links]
    append_skipped_links(file_path, new_links)

def remove_logged_links(file_path, links):
    """Remove URLs from a log file while preserving the remaining order."""
    if not os.path.exists(file_path):
        return
    links_to_remove = set(links)
    remaining_links = [link for link in read_links(file_path) if link not in links_to_remove]
    write_skipped_links(file_path, remaining_links)

def open_links_in_batches(file_path, batch_size, max_size_mb=None, modlist_path='modlist', skipped_output_path='skipped-output.txt'):
    """Open links in batches and wait for user input before proceeding to the next batch."""
    links = list(read_links(file_path))
    if not links:
        return

    if max_size_mb is not None:
        archive_sizes = load_archive_sizes(modlist_path)
        if archive_sizes is None:
            return
        links, skipped_links = filter_links_by_size(links, archive_sizes, max_size_mb)
        if links is None:
            return
        write_skipped_links(skipped_output_path, skipped_links)
        print(f"Skipped {len(skipped_links)} URLs larger than {max_size_mb} MB. Logged to {skipped_output_path}.")
        if not links:
            return

    total_batches = (len(links) + batch_size - 1) // batch_size
    current_batch = 1

    for start in range(0, len(links), batch_size):
        batch_links = links[start:start + batch_size]
        print(f"Opening batch {current_batch} of {total_batches}...")
        for link in batch_links:
            webbrowser.open(link)
        input("Press Enter to continue to the next batch...")
        current_batch += 1

def main():
    parser = argparse.ArgumentParser(description="Open Wabbajack download URLs in batches.")
    parser.add_argument('--file', default='output.txt', help='URL list to open (default: output.txt)')
    parser.add_argument('--modlist', default='modlist', help='Wabbajack modlist JSON used for archive sizes (default: modlist)')
    parser.add_argument('--max-size-mb', type=float, default=DEFAULT_MAX_SIZE_MB, help=f'Skip archives larger than this size in MB; use 0 to disable filtering (default: {DEFAULT_MAX_SIZE_MB})')
    parser.add_argument('--skipped-output', default='skipped-output.txt', help='File for URLs skipped by the size limit (default: skipped-output.txt)')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help=f'URLs to open at once (default: {DEFAULT_BATCH_SIZE})')
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if args.max_size_mb < 0:
        parser.error("--max-size-mb cannot be negative")

    max_size_mb = args.max_size_mb if args.max_size_mb > 0 else None
    open_links_in_batches(args.file, args.batch_size, max_size_mb, args.modlist, args.skipped_output)

if __name__ == "__main__":
    main()
