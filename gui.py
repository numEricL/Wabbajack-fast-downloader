import json
import os
import webbrowser
import zipfile
import tkinter as tk
from tkinter import filedialog, ttk
from typing import List
import sv_ttk
import ctypes
import sys

import batch_download
import extract_modlist
from extract_modlist import write_urls_to_file

LINK_OPEN_DELAY_MS = 500

class ThemeManager:
    COLORS = {
        'dark': {
            'bg': '#1a1a1a',
            'fg': '#ffffff',
            'accent': '#3d3d3d',
            'highlight': '#0078d4'
        }
    }

    @staticmethod
    def setup_theme(root: tk.Tk) -> None:
        sv_ttk.set_theme("dark")
        style = ttk.Style(root)
        colors = ThemeManager.COLORS['dark']
        
        style.configure('TFrame', background=colors['bg'])
        style.configure('TLabelframe', background=colors['bg'], padding=8, borderwidth=0)
        style.configure('TLabelframe.Label', font=('Segoe UI', 8),
                       background=colors['bg'], foreground=colors['fg'])
        style.configure('TButton', padding=4, borderwidth=0)
        style.configure('TEntry', fieldbackground=colors['accent'], borderwidth=0)
        style.configure('Horizontal.TProgressbar', thickness=4,
                       background=colors['highlight'])

class ConsoleOutput(tk.Text):
    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.config(state="disabled")

    def print(self, text: str) -> None:
        self.config(state="normal")
        self.insert(tk.END, text + "\n")
        self.see(tk.END)
        self.config(state="disabled")

class TextScrollCombo(tk.Frame):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setup_widget()

    def setup_widget(self) -> None:
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        text_frame = ttk.Frame(self)
        text_frame.grid(row=0, column=0, sticky="nsew")
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)

        self.txt = ConsoleOutput(text_frame)
        self.txt.grid(row=0, column=0, sticky="nsew")
        self.configure_text_widget()

        scrollb = ttk.Scrollbar(text_frame, command=self.txt.yview)
        scrollb.grid(row=0, column=1, sticky='nsew')
        self.txt['yscrollcommand'] = scrollb.set

    def configure_text_widget(self) -> None:
        self.txt.configure(
            bg='#1a1a1a',
            fg='#ffffff',
            font=('Consolas', 9),
            insertbackground='#ffffff',
            selectbackground='#0078d4',
            selectforeground='#ffffff',
            borderwidth=0,
            padx=8,
            pady=4
        )

    def print(self, text: str) -> None:
        self.txt.print(text)

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.output_file_path = 'output.txt'
        self.generated_output_file_path = 'output.txt'
        self.filtered_output_file_path = 'output-filtered.txt'
        self.skipped_output_file_path = 'output-skipped.txt'
        self.downloaded_output_file_path = 'output-downloaded.txt'
        self.links_amount = 0
        self.processed_links = tk.IntVar()
        self.max_size_mb = tk.StringVar(value=str(batch_download.DEFAULT_MAX_SIZE_MB))
        self.batch_size = tk.StringVar(value=str(batch_download.DEFAULT_BATCH_SIZE))
        self.links: List[str] = []
        self.next_link_index = 0
        self.is_downloading = False
        
        self.setup_window()
        self.create_widgets()

    def setup_window(self) -> None:
        self.setup_windows_specific()
        ThemeManager.setup_theme(self)
        
        self.title('Wabbajack Fast Downloader')
        self.geometry('380x480')
        self.minsize(380, 450)

    def setup_windows_specific(self) -> None:
        if sys.platform != 'win32':
            return

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            self.iconbitmap(default="icon.ico")
            
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd = self.winfo_id()
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(2)),
                ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

    def create_widgets(self):
        # Create and organize the main UI container
        self.main_container = ttk.Frame(self, padding=8)
        self.main_container.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_file_section()
        self.create_progress_section()
        self.create_console_section()

    def create_file_section(self):
        file_frame = ttk.LabelFrame(self.main_container, text="Source Files", padding=5)
        file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        file_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(file_frame, text="Modlist:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.file_path_entry = ttk.Entry(file_frame)
        self.file_path_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        browse_btn = ttk.Button(file_frame, text="Browse", command=self.browse_modlist, width=8)
        browse_btn.grid(row=0, column=2)

        ttk.Label(file_frame, text="URLs (optional):").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        self.output_path_entry = ttk.Entry(file_frame)
        self.output_path_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(5, 0))

        browse_output_btn = ttk.Button(file_frame, text="Browse", command=self.browse_output, width=8)
        browse_output_btn.grid(row=1, column=2, pady=(5, 0))

        ttk.Label(file_frame, text="Maximum size (MB, 0 disables):").grid(
            row=2, column=0, columnspan=2, sticky="e", padx=(0, 5), pady=(8, 0)
        )
        ttk.Entry(file_frame, textvariable=self.max_size_mb, width=8).grid(row=2, column=2, pady=(8, 0))

        filter_btn = ttk.Button(file_frame, text="Build Filter", command=self.build_filtered_output, width=15)
        filter_btn.grid(row=3, column=1, pady=(8, 0))

    def create_progress_section(self):
        # Create the download progress section
        # Contains progress bar and download button
        progress_frame = ttk.LabelFrame(self.main_container, text="Download Progress", padding=5)
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(
            progress_frame,
            orient=tk.HORIZONTAL,
            style='text.Horizontal.TProgressbar',
            length=200,
            maximum=self.links_amount,
            variable=self.processed_links
        )
        self.progress.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))

        batch_size_frame = ttk.Frame(progress_frame)
        batch_size_frame.grid(row=1, column=0, pady=(0, 5))
        ttk.Label(batch_size_frame, text="Batch size:").grid(row=0, column=0, padx=(0, 5))
        ttk.Entry(batch_size_frame, textvariable=self.batch_size, width=8).grid(row=0, column=1)

        self.download_btn = ttk.Button(
            progress_frame,
            text="Download Next Batch",
            command=self.download_links,
            width=20
        )
        self.download_btn.grid(row=2, column=0, pady=(5, 0))

    def create_console_section(self):
        # Create the console output section
        # Contains scrollable text area for logging
        console_frame = ttk.LabelFrame(self.main_container, text="Output", padding=5)
        console_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(0, weight=1)

        self.console = TextScrollCombo(console_frame)
        self.console.grid(row=0, column=0, sticky="nsew")

        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(2, weight=1)

    def update_progress_bar(self) -> None:
        style = ttk.Style()
        style.configure('text.Horizontal.TProgressbar',
                       text=f"{self.processed_links.get()}/{self.links_amount}")

    def browse_modlist(self):
        """Open a file dialog to select a Wabbajack modlist archive or JSON file."""
        filename = filedialog.askopenfilename(
            filetypes=[("Wabbajack modlist", "*.wabbajack"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(tk.END, filename)

    def browse_output(self):
        """Open a file dialog to select the source URL list."""
        filename = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if filename:
            self.output_path_entry.delete(0, tk.END)
            self.output_path_entry.insert(tk.END, filename)

    def import_links(self, file_path) -> None:
        self.processed_links.set(0)
        self.next_link_index = 0
        try:
            self.console.print(f"Importing URLs from {file_path}...")
            self.links = list(batch_download.read_links(file_path))
            self.links_amount = len(self.links)
            if self.links_amount == 0:
                self.console.print(f"No URLs found in {file_path}.")
                return
                
            self.progress['maximum'] = self.links_amount
            self.update_progress_bar()
            self.console.print(f"Imported {self.links_amount} URLs.")
        except FileNotFoundError:
            self.console.print(f"Error: The file {self.output_file_path} was not found.")
        except Exception as e:
            self.console.print(f"Error importing URLs: {e}")

    def download_links(self):
        """
        Starts automatic batch downloading.
        """
        if self.is_downloading:
            return
        if not self.links:
            self.console.print("No URLs to download. Build a filtered output file first.")
            return
        if self.links_amount == 0 or self.processed_links.get() == self.links_amount:
            self.console.print("No URLs to open.")
            return
        self.is_downloading = True
        self.download_btn.state(["disabled"])
        self.open_current_batch()

    def open_current_batch(self):
        """Open one batch and wait for the user before opening another."""
        if self.next_link_index >= len(self.links):
            self.finish_downloading()
            return
        batch_links = self.get_batch()
        if batch_links is None:
            self.finish_downloading()
            return
        self.open_next_link(iter(batch_links), [])

    def open_next_link(self, links, opened_links):
        """Open one link, then schedule the next link in the current batch."""
        try:
            link = next(links)
        except StopIteration:
            batch_download.append_new_links(self.downloaded_output_file_path, opened_links)
            self.console.print(f"Opened {self.processed_links.get()} out of {self.links_amount} URLs.")
            self.finish_downloading()
            return

        try:
            opened = webbrowser.open(link)
        except (OSError, webbrowser.Error) as error:
            opened = False
            self.console.print(f"Error opening {link}: {error}")

        if opened:
            opened_links.append(link)
        else:
            self.console.print(f"Error: Could not open {link}.")
        self.processed_links.set(self.processed_links.get() + 1)
        self.update_progress_bar()
        self.after(LINK_OPEN_DELAY_MS, self.open_next_link, links, opened_links)

    def finish_downloading(self):
        """Restore the download button after all queued URLs are processed."""
        self.is_downloading = False
        self.download_btn.state(["!disabled"])
        self.update_progress_bar()
        self.console.print(f"Finished the current batch. Opened {self.processed_links.get()} URLs.")

    def get_batch(self):
        """
        Returns the next batch of URLs using the current batch-size setting.
        """
        try:
            batch_size = int(self.batch_size.get())
        except ValueError:
            self.console.print("Error: Batch size must be a whole number.")
            return None
        if batch_size < 1:
            self.console.print("Error: Batch size must be at least 1.")
            return None

        batch = self.links[self.next_link_index:self.next_link_index + batch_size]
        self.next_link_index += len(batch)
        return batch

    def load_modlist(self, filename):
        """Load a modlist from either a Wabbajack archive or a JSON file."""
        if zipfile.is_zipfile(filename):
            with zipfile.ZipFile(filename, 'r') as zip_file:
                with zip_file.open("modlist", 'r') as metadata:
                    return json.loads(metadata.read().decode('utf-8').replace("'", '"'))
        with open(filename, 'r') as file:
            return json.load(file)

    def configure_output_paths(self, modlist_path):
        """Keep generated files next to the selected modlist."""
        output_directory = os.path.dirname(os.path.abspath(modlist_path))
        self.generated_output_file_path = os.path.join(output_directory, "output.txt")
        self.filtered_output_file_path = os.path.join(output_directory, "output-filtered.txt")
        self.skipped_output_file_path = os.path.join(output_directory, "output-skipped.txt")
        self.downloaded_output_file_path = os.path.join(output_directory, "output-downloaded.txt")

    def build_filtered_output(self):
        """Build the filtered URL list from the selected source files."""
        try:
            filename = self.file_path_entry.get()
            source_file_path = self.output_path_entry.get().strip()
            if not filename:
                self.console.print("Error: Select a modlist file.")
                return
            self.configure_output_paths(filename)
            modlist_file = self.load_modlist(filename)
            if source_file_path:
                self.output_file_path = source_file_path
                source_urls = list(batch_download.read_links(source_file_path))
                if not source_urls:
                    self.console.print(f"No URLs found in {source_file_path}.")
                    return
            else:
                self.output_file_path = self.generated_output_file_path
                source_urls = [
                    url for entry in modlist_file.get("Archives", [])
                    if (url := extract_modlist.generate_url(entry))
                ]
                write_urls_to_file(source_urls, self.output_file_path)
                self.console.print(f"Generated {len(source_urls)} URLs in {self.output_file_path}.")
            self.filter_urls(modlist_file, source_urls)
        except Exception as e:
            self.console.print("Error when building the filtered output: " + e.__str__())

    def filter_urls(self, modlist_file, source_urls=None):
        """
        Filters URLs from output.txt using the archive sizes in a modlist file.

        :param modlist_file: A JSON object representing the content of a Wabbajack
            mod list file.
        :type modlist_file: dict
        """
        try:
            max_size_mb = float(self.max_size_mb.get())
        except ValueError:
            self.console.print("Error: Maximum size must be a number.")
            return
        if max_size_mb < 0:
            self.console.print("Error: Maximum size cannot be negative.")
            return

        downloaded_urls = (
            set(batch_download.read_links(self.downloaded_output_file_path))
            if os.path.exists(self.downloaded_output_file_path)
            else set()
        )
        if source_urls is None:
            source_urls = batch_download.read_links(self.output_file_path)
        source_urls = [url for url in dict.fromkeys(source_urls) if url not in downloaded_urls]
        if not source_urls:
            self.console.print("No unprocessed URLs found in the selected source file.")
            return

        archive_sizes = batch_download.archive_sizes_from_archives(modlist_file.get("Archives", []))
        if max_size_mb == 0:
            filtered_urls, skipped_urls = source_urls, []
        else:
            filtered_urls, skipped_urls = batch_download.filter_links_by_size(
                source_urls, archive_sizes, max_size_mb
            )
            if filtered_urls is None:
                self.console.print("Error: Could not match every source URL to its archive size.")
                return

        write_urls_to_file(filtered_urls, self.filtered_output_file_path)
        batch_download.remove_logged_links(
            self.skipped_output_file_path, downloaded_urls | set(filtered_urls)
        )
        batch_download.append_new_links(self.skipped_output_file_path, skipped_urls)
        self.console.print(
            f"Wrote {len(filtered_urls)} eligible URLs to {self.filtered_output_file_path} and "
            f"logged {len(skipped_urls)} oversized URLs to {self.skipped_output_file_path}."
        )
        self.output_path_entry.delete(0, tk.END)
        self.output_path_entry.insert(0, self.filtered_output_file_path)
        self.import_links(self.filtered_output_file_path)


def main():
    app = Application()
    app.mainloop()

if __name__ == "__main__":
    main()
