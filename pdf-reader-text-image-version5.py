"""
PDF Summarization Tool
Version: 5 (Chunking + All Pages OCR)W

This application extracts text from PDF files, performs OCR on images within PDFs
(optionally on all or specific pages), and uses the DeepSeek API via chunking
to generate summaries for large documents.
"""
import os
import webbrowser
import time
import fitz  # PyMuPDF
import requests
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from PIL import Image
import pytesseract
import io
import threading
import json
from datetime import datetime
import math

# --- PDFProcessor Class ---
# Handles PDF text/image extraction and OCR execution
class PDFProcessor:
    """Handles all PDF processing operations including text extraction and OCR."""

    def __init__(self, pdf_path, ocr_lang='eng'):
        self.pdf_path = pdf_path
        self.ocr_lang = ocr_lang if ocr_lang else 'eng' # Default to english if None
        self.filename = os.path.basename(pdf_path)

    def extract_text(self):
        """Extracts plain text from all pages."""
        doc = None
        try:
            doc = fitz.open(self.pdf_path)
            text_per_page = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text_per_page.append(page.get_text())
            return text_per_page
        except Exception as e:
            raise Exception(f"Error extracting text from {self.filename}: {e}")
        finally:
            if doc:
                doc.close()

    def extract_image_text(self, page_numbers=None):
        """
        Extracts text from images on specified pages using OCR.
        If page_numbers is None, processes all pages.
        If page_numbers is an empty list, does nothing.
        """
        doc = None
        try:
            doc = fitz.open(self.pdf_path)
            text_from_images_per_page = {}
            num_pages = len(doc)

            pages_to_process = []
            if page_numbers is None: # Explicit None means process all
                pages_to_process = range(num_pages)
            elif isinstance(page_numbers, list): # Process only specified pages
                pages_to_process = [p for p in page_numbers if 0 <= p < num_pages]
                if len(pages_to_process) < len(page_numbers):
                    print(f"Warning: Some specified OCR pages were out of range for {self.filename}.")
            # If page_numbers is an empty list [], pages_to_process remains empty

            if not pages_to_process: # No pages to OCR
                return {}

            for page_num in pages_to_process:
                page = doc.load_page(page_num)
                img_list = page.get_images(full=True)
                if not img_list:
                    continue # Skip page if no images found

                text_from_images = ""
                for img_index, img in enumerate(img_list):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image = Image.open(io.BytesIO(image_bytes))
                        img_text = pytesseract.image_to_string(image, lang=self.ocr_lang)
                        if img_text.strip(): # Add only if OCR finds something
                            text_from_images += img_text + "\n"
                    except Exception as e:
                        print(f"Error processing image {img_index} on page {page_num} in {self.filename}: {e}")

                if text_from_images.strip():
                    text_from_images_per_page[page_num] = text_from_images

            return text_from_images_per_page
        except Exception as e:
            raise Exception(f"Error extracting image text from {self.filename}: {e}")
        finally:
            if doc:
                doc.close()

    def merge_text_and_images(self, pdf_text_pages, image_text_dict):
        """Merges plain text and OCR'd image text, page by page."""
        merged_text = ""
        for i, page_content in enumerate(pdf_text_pages):
            merged_text += f"--- Page {i+1} ---\n{page_content}\n"
            # Add OCR text if it exists for this page
            if i in image_text_dict and image_text_dict[i].strip():
                merged_text += f"\n[Image Text Extracted via OCR on Page {i+1}]\n{image_text_dict[i]}\n"
            merged_text += "\n"
        return merged_text.strip()

    def process(self, ocr_pages=None):
        """
        Processes the PDF: extracts text, performs OCR if needed, merges results.
        ocr_pages (None): Perform OCR on all pages with images.
        ocr_pages (list): Perform OCR only on pages in the list.
        ocr_pages ([]): Perform no OCR.
        """
        pdf_text_pages = self.extract_text()
        image_text_dict = {}

        # Decide if and where to perform OCR based on ocr_pages argument
        if ocr_pages is None or (isinstance(ocr_pages, list) and len(ocr_pages) > 0):
            # Pass None or the list to extract_image_text
            image_text_dict = self.extract_image_text(ocr_pages)
        # If ocr_pages is [], image_text_dict remains empty, no OCR is done.

        return self.merge_text_and_images(pdf_text_pages, image_text_dict)


# --- APIClient Class ---
# Handles DeepSeek API communication, including text chunking
class APIClient:
    """Handles API interactions for summarization, including chunking for large texts."""
    MAX_CHARS_PER_CHUNK = 15000
    MAX_COMBINED_SUMMARY_CHARS = 20000

    def __init__(self, api_key):
        self.api_key = api_key

    def _split_text_into_chunks(self, text):
        """Splits text into chunks smaller than MAX_CHARS_PER_CHUNK."""
        if not text or len(text) <= self.MAX_CHARS_PER_CHUNK:
            return [text] if text else []

        chunks = []
        current_pos = 0
        text_len = len(text)
        while current_pos < text_len:
            end_pos = min(current_pos + self.MAX_CHARS_PER_CHUNK, text_len)
            split_pos = end_pos

            if end_pos < text_len:
                # Try to split at natural breaks backwards from end_pos
                best_split = -1
                # Prioritize page breaks, then paragraphs, then sentences
                page_break = text.rfind("\n--- Page", current_pos, end_pos)
                if page_break > current_pos: best_split = page_break

                para_break = text.rfind("\n\n", current_pos, end_pos)
                if para_break > current_pos and para_break > best_split: best_split = para_break + 2 # Include break

                if best_split == -1: # Only look for sentences if no better break found
                    sentence_break = -1
                    for sep in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
                        found = text.rfind(sep, current_pos, end_pos)
                        if found > current_pos and found > sentence_break:
                            sentence_break = found + 1 # Position after punctuation
                    if sentence_break > current_pos: best_split = sentence_break

                if best_split > current_pos: # Found a good split point
                    split_pos = best_split
                # else: Keep split_pos = end_pos (hard split)

            chunk = text[current_pos:split_pos].strip()
            if chunk: # Avoid adding empty strings
                chunks.append(chunk)
            current_pos = split_pos

            # Safety break if position doesn't advance
            if current_pos == end_pos and end_pos == text_len: break
            if current_pos >= text_len : break
            if split_pos <= current_pos and current_pos < text_len:
                # If stuck, force advance by taking the max chunk size or remaining text
                print("Warning: Forcing split advancement.")
                force_end = min(current_pos + self.MAX_CHARS_PER_CHUNK, text_len)
                chunk = text[current_pos:force_end].strip()
                if chunk: chunks.append(chunk)
                current_pos = force_end


        return [c for c in chunks if c] # Final filter for empty chunks

    def _send_api_request(self, prompt_content, context_info=""):
        """Sends a single request to the DeepSeek API."""
        if not self.api_key:
            return "Error: API Key not provided to APIClient."

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        full_prompt = f"{context_info}\n\n{prompt_content}".strip()
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": full_prompt}],
            # Consider adding temperature or other parameters if needed
            # "temperature": 0.7,
        }

        response_data = None # Initialize for error reporting
        try:
            response = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers=headers, json=data, timeout=180 # Longer timeout
            )
            response.raise_for_status()
            response_data = response.json()

            if response_data and 'choices' in response_data and response_data['choices']:
                message = response_data['choices'][0].get('message', {})
                content = message.get('content')
                if content:
                    return content.strip()
                else:
                    finish_reason = response_data['choices'][0].get('finish_reason')
                    # Handle potential content filtering or length issues explicitly
                    if finish_reason == 'content_filter':
                        return "Error: API response filtered due to content policy."
                    elif finish_reason == 'length':
                        return "Error: API response truncated due to length limits. Consider reducing chunk size or summary detail."
                    else:
                        print(f"API Warning: Response received but content is missing. Finish Reason: {finish_reason}. Data: {response_data}")
                        return f"Error: API returned empty content (Finish Reason: {finish_reason})."
            else:
                print(f"API Error: Unexpected response structure. Data: {response_data}")
                return f"Error: Unexpected API response format. Data: {response_data}"

        except requests.exceptions.Timeout:
            return "Error: Request timed out. Check connection or increase timeout."
        except requests.exceptions.HTTPError as err:
            error_detail = f"Status Code: {err.response.status_code}"
            try:
                error_body = err.response.json()
                error_detail += f", Response: {error_body}"
            except json.JSONDecodeError:
                error_detail += f", Response: {err.response.text}"
            return f"Error: HTTP Error: {err}. {error_detail}"
        except requests.exceptions.RequestException as err:
            return f"Error: Network or Request Error: {err}"
        except (KeyError, ValueError, AttributeError) as err:
            print(f"Error processing API response: {err}. Response data: {response_data}")
            return f"Error: Could not parse API response: {err}"
        except Exception as e: # Catch any other unexpected errors
            print(f"Unexpected error during API request: {e}")
            return f"Error: An unexpected error occurred: {e}"

    def summarize_text(self, text, custom_instruction, update_status_callback=None):
        """Summarizes text, handling chunking and final synthesis."""
        if not text or not text.strip():
            return "Error: No text provided to summarize."

        if update_status_callback: update_status_callback("Splitting text into chunks...")
        chunks = self._split_text_into_chunks(text)
        num_chunks = len(chunks)

        if num_chunks == 0:
            return "Error: Text resulted in zero valid chunks after splitting."
        if update_status_callback: update_status_callback(f"Text split into {num_chunks} chunk(s).")

        if num_chunks == 1:
            if update_status_callback: update_status_callback("Summarizing single chunk...")
            prompt = f"{custom_instruction}\n\nPlease summarize the following text:\n\n{chunks[0]}"
            summary = self._send_api_request(prompt)
            if update_status_callback: update_status_callback("Summary received." if not summary.startswith("Error:") else summary)
            return summary
        else:
            # Summarize chunks individually
            chunk_summaries = []
            has_errors = False
            for i, chunk in enumerate(chunks):
                chunk_num = i + 1
                if update_status_callback: update_status_callback(f"Summarizing chunk {chunk_num}/{num_chunks}...")

                context_info = f"You are summarizing part {chunk_num} of {num_chunks} from a larger document."
                prompt = f"{custom_instruction}\n\nPlease summarize this section of the document:\n\n{chunk}"
                chunk_summary = self._send_api_request(prompt, context_info)

                if chunk_summary.startswith("Error:"):
                    print(f"Warning: Failed to summarize chunk {chunk_num}. Error: {chunk_summary}")
                    # Append error message to potentially include in final output or just log
                    chunk_summaries.append(f"[Error summarizing chunk {chunk_num}: {chunk_summary}]")
                    has_errors = True
                else:
                    chunk_summaries.append(chunk_summary)
                time.sleep(0.5) # Small delay between API calls

            if not chunk_summaries:
                return "Error: Failed to get summaries for any chunk."

            # Combine chunk summaries
            combined_summaries_text = "\n\n---\n\n".join(chunk_summaries)

            # Check if combined summaries are short enough for final synthesis
            if len(combined_summaries_text) > self.MAX_COMBINED_SUMMARY_CHARS or has_errors:
                prefix = "--- Combined Section Summaries (Final Synthesis Skipped Due to Length or Chunk Errors) ---\n\n"
                if update_status_callback: update_status_callback("Combined summaries too long or errors occurred. Returning combined summaries.")
                return prefix + combined_summaries_text
            else:
                # Perform final synthesis
                if update_status_callback: update_status_callback("Combining chunk summaries for final result...")
                final_prompt = (
                    f"The following are summaries of consecutive sections of a document. "
                    f"Synthesize them into a single, coherent, and comprehensive summary of the entire document, "
                    f"maintaining a consistent tone and flow.\n\n"
                    f"The original high-level instruction for the summary was: '{custom_instruction}'\n\n"
                    f"--- Individual Section Summaries to Combine ---\n{combined_summaries_text}"
                )
                final_summary = self._send_api_request(final_prompt)
                if update_status_callback: update_status_callback("Final summary received." if not final_summary.startswith("Error:") else final_summary)
                return final_summary


# --- ConfigManager Class ---
# Manages loading/saving application settings
class ConfigManager:
    """Manages application configuration and settings."""
    def __init__(self, config_file="pdf_summarizer_config.json"):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        """Loads configuration from file, merging with defaults."""
        default_config = {
            "api_key": "", # Never loaded/saved from/to file
            "folder_path": "",
            "custom_instruction": "Summarize this document and highlight key points.",
            "ocr_language": "eng",
            "ocr_pages": "0,1",      # Specific pages string
            "ocr_all_pages": False,  # Boolean for 'All Pages' checkbox
            "recent_folders": [],
            "auto_open_pdf": True,
            "default_save_location": ""
        }
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved_config = json.load(f)
                    config = {**default_config, **saved_config}
                    config["api_key"] = "" # Ensure API key isn't loaded
                    return config
            return default_config
        except (json.JSONDecodeError, IOError, Exception) as e:
            print(f"Error loading config file '{self.config_file}': {e}. Using defaults.")
            return default_config

    def save_config(self):
        """Saves configuration to file, excluding API key."""
        try:
            config_to_save = self.config.copy()
            if "api_key" in config_to_save:
                del config_to_save["api_key"] # Never save API key

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)
        except (IOError, Exception) as e:
            print(f"Error saving config file '{self.config_file}': {e}")

    def update_config(self, key, value):
        """Updates a config value and saves (unless it's the API key)."""
        self.config[key] = value
        if key != "api_key":
            self.save_config()

    def get_config(self, key, default=None):
        """Safely gets a configuration value."""
        return self.config.get(key, default)

    def add_recent_folder(self, folder_path):
        """Adds a folder to the recent list."""
        if not folder_path or not os.path.isdir(folder_path): return
        recent = self.config.get("recent_folders", [])
        if folder_path in recent: recent.remove(folder_path)
        recent.insert(0, folder_path)
        self.config["recent_folders"] = recent[:5] # Keep last 5
        self.save_config() # Save changes


# --- SummaryWindow Class ---
# Displays the generated summary in a separate window
class SummaryWindow:
    """Window for displaying and saving summaries."""
    def __init__(self, summary, pdf_file, default_save_dir=""):
        self.summary = summary
        self.pdf_file = pdf_file
        # Use provided default dir, fallback to cwd if invalid or not provided
        self.default_save_dir = default_save_dir if default_save_dir and os.path.isdir(default_save_dir) else os.getcwd()
        self.window = tk.Toplevel()
        self.window.title(f"Summary - {pdf_file}")
        self.window.geometry("800x600")
        # Set window to be transient to the main window if possible (optional)
        # try: self.window.transient(root) except NameError: pass
        self.create_widgets()
        self.window.lift() # Bring window to front
        self.window.focus_force() # Force focus


    def create_widgets(self):
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        self.text_box = scrolledtext.ScrolledText(
            main_frame, wrap=tk.WORD, font=("Arial", 11), relief=tk.FLAT, borderwidth=0, state=tk.NORMAL # Start as normal to insert
        )
        self.text_box.grid(row=0, column=0, sticky="nsew")

        scroll_bar = ttk.Scrollbar(main_frame, orient="vertical", command=self.text_box.yview)
        scroll_bar.grid(row=0, column=1, sticky="ns")
        self.text_box["yscrollcommand"] = scroll_bar.set

        self.text_box.tag_configure("title", font=("Arial", 13, "bold"), foreground="#003366")
        self.text_box.insert(tk.END, f"Summary for: {self.pdf_file}\n\n", "title")
        self.text_box.insert(tk.END, self.summary if self.summary else "No summary content generated.")
        self.text_box.config(state=tk.DISABLED) # Make read-only after inserting

        button_frame = ttk.Frame(self.window, padding=(10, 5, 10, 10)) # Reduced top padding
        button_frame.grid(row=1, column=0, sticky="ew")
        button_frame.columnconfigure(1, weight=1)

        save_button = ttk.Button(button_frame, text="Save Summary", command=self.save_summary, style='Accent.TButton') # Example style
        save_button.grid(row=0, column=0, padx=(0, 5))

        copy_button = ttk.Button(button_frame, text="Copy to Clipboard", command=self.copy_to_clipboard)
        copy_button.grid(row=0, column=1, padx=5, sticky="w")

        close_button = ttk.Button(button_frame, text="Close", command=self.window.destroy)
        close_button.grid(row=0, column=2, sticky="e")

    def save_summary(self):
        """Saves the summary content to a text file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize filename slightly
        safe_pdf_name = "".join(c for c in os.path.splitext(self.pdf_file)[0] if c.isalnum() or c in (' ', '_', '-')).rstrip()
        default_filename = f"{safe_pdf_name}_summary_{timestamp}.txt"

        file_path = filedialog.asksaveasfilename(
            parent=self.window, # Make dialog modal to this window
            initialdir=self.default_save_dir,
            initialfile=default_filename,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(f"Summary for: {self.pdf_file}\n")
                    file.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    file.write(self.summary)
                messagebox.showinfo("Success", f"Summary saved successfully to:\n{file_path}", parent=self.window)
            except (IOError, Exception) as e:
                messagebox.showerror("Error", f"Failed to save file:\n{e}", parent=self.window)

    def copy_to_clipboard(self):
        """Copies the summary text to the system clipboard."""
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.summary)
            messagebox.showinfo("Success", "Summary copied to clipboard.", parent=self.window)
        except tk.TclError:
            messagebox.showwarning("Clipboard Error", "Could not access the clipboard.", parent=self.window)


# --- Application Class ---
# Main GUI application logic
class Application:
    """Main application class."""
    APP_VERSION = "v2.2"

    def __init__(self, root):
        self.root = root
        self.root.title(f"PDF Summarization Tool {self.APP_VERSION}")
        self.root.geometry("580x520") # Adjusted size for new widget
        self.root.minsize(550, 480) # Minimum size

        self.config_manager = ConfigManager()
        self.running = False
        self.current_task_thread = None

        # --- Setup Style ---
        style = ttk.Style()
        available_themes = style.theme_names()
        # Prefer 'clam', 'vista', or 'xpnative' if available for a slightly more modern look
        preferred_themes = ['clam', 'vista', 'xpnative']
        for theme in preferred_themes:
            if theme in available_themes:
                try:
                    style.theme_use(theme)
                    break
                except tk.TclError:
                    continue
        style.configure('TButton', padding=5)
        style.configure('TEntry', padding=(2, 3)) # Less vertical padding for entry
        style.configure('TLabel', padding=(5, 2))
        style.configure('TCheckbutton', padding=3)
        style.configure('TCombobox', padding=2)
        style.configure('TLabelframe.Label', font=('Arial', 10, 'bold'))
        style.configure('Accent.TButton', foreground='white', background='#0078D4') # Example accent button


        # --- Create Widgets ---
        self.create_widgets()
        self.load_saved_values()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """Creates and arranges all GUI widgets."""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1) # Allow notebook to expand

        self.notebook = ttk.Notebook(self.root, padding=(5, 5, 5, 0)) # Add padding around notebook
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0)) # Pad below notebook

        # --- Main Tab ---
        self.main_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.main_tab, text=" Main ") # Add spaces for visual padding
        self.main_tab.columnconfigure(1, weight=1) # Make entry/combo column expandable

        # Row 0: API Key
        ttk.Label(self.main_tab, text="DeepSeek API Key:").grid(row=0, column=0, sticky="w")
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(self.main_tab, textvariable=self.api_key_var, width=40, show="*")
        self.api_key_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.show_key_var = tk.BooleanVar(value=False)
        self.show_key_button = ttk.Checkbutton(self.main_tab, text="Show", variable=self.show_key_var, command=self.toggle_show_api_key, width=5)
        self.show_key_button.grid(row=0, column=2, padx=(0,5)) # Reduce right pad

        # Row 1: Folder Path
        ttk.Label(self.main_tab, text="PDF Folder:").grid(row=1, column=0, sticky="w")
        self.folder_path_var = tk.StringVar()
        self.folder_path_entry = ttk.Entry(self.main_tab, textvariable=self.folder_path_var, width=40)
        self.folder_path_entry.grid(row=1, column=1, sticky="ew", padx=5)
        browse_button = ttk.Button(self.main_tab, text="Browse...", command=self.browse_folder)
        browse_button.grid(row=1, column=2, padx=(0,5))

        # Row 2: Recent Folders
        ttk.Label(self.main_tab, text="Recent:").grid(row=2, column=0, sticky="w")
        self.recent_folders_var = tk.StringVar()
        self.recent_folders_dropdown = ttk.Combobox(self.main_tab, textvariable=self.recent_folders_var, state="readonly", width=38)
        self.recent_folders_dropdown.grid(row=2, column=1, sticky="ew", padx=5)
        self.recent_folders_dropdown.bind("<<ComboboxSelected>>", self.select_recent_folder)

        # Row 3: Custom Instruction
        ttk.Label(self.main_tab, text="Instruction:", anchor='nw').grid(row=3, column=0, sticky="nw", pady=(5,0))
        self.instruction_text = scrolledtext.ScrolledText(self.main_tab, height=3, width=40, wrap=tk.WORD, relief=tk.SUNKEN, borderwidth=1, font=('Arial', 10))
        self.instruction_text.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=(5,5))

        # Row 4: OCR Settings Frame
        ocr_frame = ttk.LabelFrame(self.main_tab, text="OCR Settings", padding="10")
        ocr_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        ocr_frame.columnconfigure(1, weight=1)

        self.ocr_enabled_var = tk.BooleanVar(value=True) # Default OCR enabled
        self.ocr_enabled_check = ttk.Checkbutton(ocr_frame, text="Enable OCR on Images", variable=self.ocr_enabled_var, command=self.toggle_ocr_settings)
        self.ocr_enabled_check.grid(row=0, column=0, columnspan=3, sticky="w", padx=(0,5), pady=(0,5)) # Span across

        # Frame to hold the conditional OCR controls
        self.ocr_widgets_frame = ttk.Frame(ocr_frame)
        self.ocr_widgets_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.ocr_widgets_frame.columnconfigure(1, weight=1)

        # -- Controls within ocr_widgets_frame --
        # All Pages Checkbox
        self.ocr_all_pages_var = tk.BooleanVar(value=False)
        self.ocr_all_pages_check = ttk.Checkbutton(self.ocr_widgets_frame, text="All Pages", variable=self.ocr_all_pages_var, command=self.toggle_ocr_all_pages)
        self.ocr_all_pages_check.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        # Specific Pages Label & Entry (conditionally enabled)
        ttk.Label(self.ocr_widgets_frame, text="Specific Pages (if not 'All'):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.ocr_pages_var = tk.StringVar()
        self.ocr_pages_entry = ttk.Entry(self.ocr_widgets_frame, textvariable=self.ocr_pages_var, width=25)
        self.ocr_pages_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        # Language Label & Combobox
        ttk.Label(self.ocr_widgets_frame, text="Language (Tesseract):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.ocr_lang_var = tk.StringVar()
        self.ocr_lang_combo = ttk.Combobox(self.ocr_widgets_frame, textvariable=self.ocr_lang_var,
                                           values=["eng", "chi_sim", "fra", "deu", "spa", "jpn", "kor", "eng+chi_sim"], width=15, state='readonly')
        self.ocr_lang_combo.grid(row=2, column=1, sticky="w", padx=5, pady=2) # Align left

        # Row 5: Status and Progress Frame
        status_frame = ttk.Frame(self.main_tab)
        status_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=5, pady=(10, 5)) # Add top padding
        status_frame.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w")
        status_label.grid(row=0, column=0, sticky="ew", padx=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, length=200, mode='determinate')
        self.progress_bar.grid(row=0, column=1, padx=5, sticky='e')

        # Row 6: Run Button Frame (to center the button)
        run_button_frame = ttk.Frame(self.main_tab)
        run_button_frame.grid(row=6, column=0, columnspan=3, pady=(5, 10)) # Add top/bottom padding
        run_button_frame.columnconfigure(0, weight=1) # Center the button
        self.run_button = ttk.Button(run_button_frame, text="Start Processing", command=self.run_task, style='Accent.TButton', width=20)
        self.run_button.grid(row=0, column=0)

        # --- Settings Tab ---
        self.settings_tab = ttk.Frame(self.notebook, padding="15") # More padding for settings
        self.notebook.add(self.settings_tab, text=" Settings ")
        self.setup_settings_tab()

        # Call toggles AFTER all widgets are created
        self.toggle_ocr_settings()

    def setup_settings_tab(self):
        """Sets up the widgets within the Settings tab."""
        self.settings_tab.columnconfigure(1, weight=1)

        # Section Title: Application Settings
        ttk.Label(self.settings_tab, text="Application Settings", font=('Arial', 11, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        # Auto-open PDF Checkbox
        self.auto_open_pdf_var = tk.BooleanVar()
        ttk.Checkbutton(self.settings_tab, text="Open PDF files automatically after processing",
                        variable=self.auto_open_pdf_var).grid(row=1, column=0, columnspan=3, sticky="w", pady=2)

        # Default Save Location Label, Entry, and Button
        ttk.Label(self.settings_tab, text="Default save location for summaries:").grid(row=2, column=0, sticky="w", pady=2)
        self.save_location_var = tk.StringVar()
        save_loc_entry = ttk.Entry(self.settings_tab, textvariable=self.save_location_var, width=40)
        save_loc_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(self.settings_tab, text="Browse...", command=self.browse_save_location).grid(row=2, column=2, padx=(0,5), pady=2)

        # Separator
        ttk.Separator(self.settings_tab, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="ew", pady=15)

        # Section Title: About
        ttk.Label(self.settings_tab, text="About", font=('Arial', 11, "bold")).grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 5))
        about_text = (
            f"PDF Summarization Tool {self.APP_VERSION}\n\n"
            "Uses PyMuPDF for text/image extraction, Pytesseract for OCR, "
            "and the DeepSeek API for summarization.\nHandles large documents "
            "by splitting text into chunks."
        )
        about_label = ttk.Label(self.settings_tab, text=about_text, wraplength=450, justify="left")
        about_label.grid(row=5, column=0, columnspan=3, sticky="w", pady=5)

        # Save Settings Button (placed using pack for centering in a frame)
        self.settings_tab.rowconfigure(6, weight=1) # Push button down
        button_container = ttk.Frame(self.settings_tab)
        button_container.grid(row=7, column=0, columnspan=3, pady=(20, 0)) # Span and pad top
        save_settings_button = ttk.Button(button_container, text="Save Settings", command=self.save_settings, width=15)
        save_settings_button.pack() # Pack centers the button in its frame


    def load_saved_values(self):
        """Loads configuration values from ConfigManager into UI variables."""
        self.folder_path_var.set(self.config_manager.get_config("folder_path", ""))
        # Load instruction into ScrolledText (clear first)
        self.instruction_text.delete('1.0', tk.END)
        self.instruction_text.insert('1.0', self.config_manager.get_config("custom_instruction", "Summarize this document and highlight key points."))

        self.ocr_lang_var.set(self.config_manager.get_config("ocr_language", "eng"))
        self.ocr_pages_var.set(self.config_manager.get_config("ocr_pages", "0,1"))
        self.ocr_all_pages_var.set(self.config_manager.get_config("ocr_all_pages", False)) # Load 'All Pages' state
        self.auto_open_pdf_var.set(self.config_manager.get_config("auto_open_pdf", True))
        self.save_location_var.set(self.config_manager.get_config("default_save_location", ""))

        self.update_recent_folders_dropdown()
        # Update UI states AFTER loading all values
        self.toggle_ocr_settings()


    def update_recent_folders_dropdown(self):
        """Updates the recent folders dropdown."""
        recent_folders = self.config_manager.get_config("recent_folders", [])
        self.recent_folders_dropdown["values"] = recent_folders if recent_folders else [""]
        if not recent_folders: self.recent_folders_var.set("")


    def select_recent_folder(self, event=None): # Added event=None for direct calls
        """Handles selection from recent folders dropdown."""
        selected = self.recent_folders_var.get()
        if selected and os.path.isdir(selected):
            self.folder_path_var.set(selected)
            # Optional: Clear selection display after applying
            # self.recent_folders_var.set("")


    def toggle_show_api_key(self):
        """Toggles visibility of the API key entry."""
        self.api_key_entry.config(show="" if self.show_key_var.get() else "*")


    def toggle_ocr_all_pages(self):
        """Enables/disables the specific page entry based on 'All Pages' state."""
        # This is called when the 'All Pages' checkbox is clicked
        is_all_pages = self.ocr_all_pages_var.get()
        ocr_is_enabled = self.ocr_enabled_var.get()

        if is_all_pages and ocr_is_enabled:
            self.ocr_pages_entry.config(state=tk.DISABLED)
        elif not is_all_pages and ocr_is_enabled:
            self.ocr_pages_entry.config(state=tk.NORMAL)
        else: # If OCR is disabled, pages entry should also be disabled
            self.ocr_pages_entry.config(state=tk.DISABLED)


    def toggle_ocr_settings(self):
        """Enables/disables all OCR controls based on the main 'Enable OCR' checkbox."""
        # This is called when the 'Enable OCR' checkbox is clicked
        ocr_is_enabled = self.ocr_enabled_var.get()
        new_state = tk.NORMAL if ocr_is_enabled else tk.DISABLED

        # Enable/disable all widgets within the dedicated frame
        for widget in self.ocr_widgets_frame.winfo_children():
            try:
                # Labels don't have state, skip them directly
                if not isinstance(widget, ttk.Label):
                    widget.config(state=new_state)
            except tk.TclError:
                pass # Ignore other potential widget types without state

        # Crucially, after setting the bulk state, fix the specific pages entry
        # based on the 'All Pages' checkbox, but only if OCR is now enabled.
        if ocr_is_enabled:
            self.toggle_ocr_all_pages() # This re-evaluates entry state
        else:
            # Ensure entry is disabled if OCR is disabled
            self.ocr_pages_entry.config(state=tk.DISABLED)


    def browse_folder(self):
        """Opens folder browser dialog for selecting the PDF folder."""
        # Use last selected path or current working directory as starting point
        initial_dir = self.folder_path_var.get() or os.getcwd()
        folder_path = filedialog.askdirectory(initialdir=initial_dir, title="Select Folder Containing PDFs")
        if folder_path:
            self.folder_path_var.set(folder_path)


    def browse_save_location(self):
        """Opens folder browser dialog for selecting default summary save location."""
        initial_dir = self.save_location_var.get() or os.getcwd()
        folder_path = filedialog.askdirectory(initialdir=initial_dir, title="Select Default Save Location for Summaries")
        if folder_path:
            self.save_location_var.set(folder_path)


    def save_settings(self):
        """Saves current UI settings to the configuration file."""
        # Get values from UI elements
        self.config_manager.update_config("folder_path", self.folder_path_var.get())
        self.config_manager.update_config("custom_instruction", self.instruction_text.get("1.0", tk.END).strip())
        self.config_manager.update_config("ocr_language", self.ocr_lang_var.get())
        self.config_manager.update_config("ocr_pages", self.ocr_pages_var.get())
        self.config_manager.update_config("ocr_all_pages", self.ocr_all_pages_var.get()) # Save 'All Pages' state
        self.config_manager.update_config("auto_open_pdf", self.auto_open_pdf_var.get())
        self.config_manager.update_config("default_save_location", self.save_location_var.get())

        messagebox.showinfo("Settings Saved", "Settings have been saved successfully.\n(API Key is not saved to file).")


    def parse_ocr_pages(self, pages_str):
        """Parses the OCR pages string (e.g., "0,1,5-8,10") into a list of integers."""
        pages = set()
        if not pages_str or not pages_str.strip():
            return [] # Return empty list if input is empty or whitespace

        parts = pages_str.split(',')
        for part in parts:
            part = part.strip()
            if not part: continue
            try:
                if '-' in part:
                    start_end = part.split('-')
                    if len(start_end) != 2: raise ValueError("Range must be in 'start-end' format.")
                    start, end = map(int, start_end)
                    if start < 0 or end < 0: raise ValueError("Page numbers cannot be negative.")
                    if start > end: raise ValueError(f"Invalid range: start ({start}) > end ({end})")
                    pages.update(range(start, end + 1))
                else:
                    page_num = int(part)
                    if page_num < 0: raise ValueError("Page numbers cannot be negative.")
                    pages.add(page_num)
            except ValueError as e:
                # More specific error message
                error_detail = str(e)
                if "invalid literal" in error_detail: error_detail = "contains non-numeric characters"
                raise ValueError(f"Invalid page format '{part}': {error_detail}. Use numbers, commas, and hyphens (e.g., 0,1,5-8).") from e
        return sorted(list(pages))


    def update_status(self, message):
        """Thread-safe way to update the status label."""
        # Check if root window exists before scheduling update
        if self.root and self.root.winfo_exists():
            self.root.after(0, lambda: self.status_var.set(message))


    def update_progress(self, value):
        """Thread-safe way to update the progress bar."""
        if self.root and self.root.winfo_exists():
            self.root.after(0, lambda: self.progress_var.set(value))


    def run_task(self):
        """Validates inputs and starts the PDF processing task in a separate thread."""
        if self.running:
            messagebox.showwarning("Task Running", "A processing task is already in progress.", parent=self.root)
            return

        # --- Input Validation ---
        api_key = self.api_key_var.get()
        folder_path = self.folder_path_var.get()

        if not api_key:
            messagebox.showerror("Missing Input", "Please enter your DeepSeek API key.", parent=self.root)
            self.notebook.select(self.main_tab)
            self.api_key_entry.focus()
            return

        if not folder_path or not os.path.isdir(folder_path):
            messagebox.showerror("Invalid Input", "Please select a valid folder containing PDF files.", parent=self.root)
            self.notebook.select(self.main_tab)
            self.folder_path_entry.focus()
            return

        # --- Get PDF Files ---
        try:
            pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(folder_path, f))]
        except OSError as e:
            messagebox.showerror("Folder Error", f"Could not read PDF folder:\n{e}", parent=self.root)
            return

        if not pdf_files:
            messagebox.showinfo("No PDFs Found", "No PDF files were found in the selected folder.", parent=self.root)
            return

        # --- Get Settings ---
        # Save API key in memory only for this session
        self.config_manager.config["api_key"] = api_key

        ocr_enabled = self.ocr_enabled_var.get()
        ocr_all_pages = self.ocr_all_pages_var.get()
        ocr_lang = self.ocr_lang_var.get() if ocr_enabled else None
        ocr_pages_list = [] # Default to empty list (no specific pages)

        # Parse specific pages only if OCR is enabled AND 'All Pages' is NOT checked
        if ocr_enabled and not ocr_all_pages:
            try:
                ocr_pages_str = self.ocr_pages_var.get()
                ocr_pages_list = self.parse_ocr_pages(ocr_pages_str)
                # Save the potentially cleaned/validated string back to config
                self.config_manager.update_config("ocr_pages", ocr_pages_str)
            except ValueError as e:
                messagebox.showerror("Invalid OCR Pages", f"Error in OCR Pages input:\n{e}", parent=self.root)
                self.notebook.select(self.main_tab)
                self.ocr_pages_entry.focus_set()
                return
        # Save the 'All Pages' state as well
        self.config_manager.update_config("ocr_all_pages", ocr_all_pages)

        custom_instruction = self.instruction_text.get("1.0", tk.END).strip()
        auto_open = self.auto_open_pdf_var.get()
        default_save_dir = self.save_location_var.get()

        # Add folder to recent list & save current path
        self.config_manager.add_recent_folder(folder_path)
        self.update_recent_folders_dropdown()
        self.config_manager.update_config("folder_path", folder_path)

        # --- Start Thread ---
        self.running = True
        self.run_button.config(state="disabled")
        self.progress_var.set(0)
        self.progress_bar["maximum"] = len(pdf_files)
        self.status_var.set(f"Starting processing for {len(pdf_files)} PDF(s)...")

        self.current_task_thread = threading.Thread(
            target=self.process_pdfs_thread,
            args=(pdf_files, folder_path, api_key, custom_instruction,
                  ocr_enabled, ocr_all_pages, # Pass the boolean state
                  ocr_lang, ocr_pages_list, auto_open, default_save_dir),
            daemon=True
        )
        self.current_task_thread.start()


    def process_pdfs_thread(self, pdf_files, folder_path, api_key, custom_instruction,
                            ocr_enabled, ocr_all_pages, # Accept the boolean state
                            ocr_lang, ocr_pages_list, auto_open, default_save_dir):
        """Worker thread for processing PDF files sequentially."""
        try:
            api_client = APIClient(api_key)
            num_files = len(pdf_files)
            processed_count = 0
            error_count = 0

            for i, pdf_file in enumerate(pdf_files):
                if not self.running: # Allow task to be cancelled (though not explicitly implemented yet)
                    print("Processing cancelled.")
                    break

                current_file_num = i + 1
                self.update_status(f"Processing file {current_file_num}/{num_files}: {pdf_file}")
                start_time = time.time()

                try:
                    pdf_path = os.path.join(folder_path, pdf_file)

                    # --- Step 1: Extract Text (with OCR if enabled) ---
                    self.update_status(f"({current_file_num}/{num_files}) Extracting text: {pdf_file}...")
                    processor = PDFProcessor(pdf_path, ocr_lang=ocr_lang if ocr_enabled else None)

                    # Determine argument for processor.process based on OCR settings
                    pages_to_ocr_arg = [] # Default: Perform NO OCR
                    if ocr_enabled:
                        if ocr_all_pages:
                            pages_to_ocr_arg = None # Signal Processor to OCR all pages
                        else:
                            pages_to_ocr_arg = ocr_pages_list # Use specific list (might be empty)

                    text_to_summarize = processor.process(ocr_pages=pages_to_ocr_arg)

                    if not text_to_summarize or not text_to_summarize.strip():
                        print(f"Warning: No text extracted from {pdf_file}. Skipping summarization.")
                        self.update_progress(current_file_num)
                        continue # Move to next file

                    # --- Step 2: Summarize Text ---
                    self.update_status(f"({current_file_num}/{num_files}) Summarizing: {pdf_file}...")
                    summary = api_client.summarize_text(text_to_summarize, custom_instruction, self.update_status)

                    # --- Step 3: Handle Result ---
                    if summary.startswith("Error:"):
                        error_count += 1
                        # Show non-blocking error for the specific file
                        error_msg = f"Failed to summarize {pdf_file}:\n{summary}"
                        print(error_msg)
                        self.root.after(0, lambda msg=error_msg: messagebox.showwarning("Summarization Error", msg, parent=self.root))
                    else:
                        processed_count += 1
                        # Display summary (thread-safe via 'after')
                        self.root.after(0, lambda s=summary, p=pdf_file, save_dir=default_save_dir: self.show_summary(s, p, save_dir))
                        # Auto-open PDF if enabled (thread-safe via 'after')
                        if auto_open:
                            try:
                                # Use os.path.abspath for better cross-platform file URI
                                abs_path = os.path.abspath(pdf_path)
                                # Replace backslashes for file URI if on Windows
                                if os.name == 'nt': abs_path = abs_path.replace('\\', '/')
                                file_uri = f'file:///{abs_path}'
                                self.root.after(0, lambda uri=file_uri: webbrowser.open(uri))
                            except Exception as web_err:
                                print(f"Could not auto-open {pdf_path}: {web_err}")

                except Exception as e:
                    error_count += 1
                    # Log detailed error and show simplified message
                    error_msg = f"Error processing {pdf_file}:\n{type(e).__name__}: {e}"
                    print(f"\n--- Error Details for {pdf_file} ---")
                    import traceback
                    traceback.print_exc()
                    print("--- End Error Details ---\n")
                    self.root.after(0, lambda msg=error_msg: messagebox.showerror("File Processing Error", msg, parent=self.root))

                # Update progress bar after each file attempt
                self.update_progress(current_file_num)
                end_time = time.time()
                print(f"Finished processing {pdf_file} in {end_time - start_time:.2f} seconds.")
                # Optional small delay for UI responsiveness, less needed now with granular status updates
                # time.sleep(0.05)

            # --- Processing Complete ---
            final_msg = f"Processing complete.\nSuccessfully summarized: {processed_count}\nFiles with errors: {error_count}"
            self.update_status(final_msg)
            self.root.after(0, lambda: messagebox.showinfo("Processing Finished", final_msg, parent=self.root))

        except Exception as thread_err:
            # Handle unexpected errors in the thread itself
            error_msg = f"An unexpected error occurred during processing: {thread_err}"
            print(f"\n--- Thread Error ---")
            import traceback
            traceback.print_exc()
            print("--- End Thread Error ---\n")
            self.update_status(f"Critical Error: {thread_err}")
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Critical Error", msg, parent=self.root))

        finally:
            # Reset UI state regardless of success or failure (thread-safe)
            self.running = False
            if self.root and self.root.winfo_exists():
                self.root.after(0, lambda: self.run_button.config(state="normal"))
                self.root.after(0, lambda: self.progress_var.set(0)) # Optionally reset progress
            self.current_task_thread = None


    def show_summary(self, summary, pdf_file, default_save_dir):
        """Creates and displays the summary window (called from main thread)."""
        if self.root and self.root.winfo_exists():
            SummaryWindow(summary, pdf_file, default_save_dir)


    def on_close(self):
        """Handles application closing action."""
        if self.running:
            if messagebox.askokcancel("Confirm Quit", "A task is currently running. Quitting now will abruptly stop the process.\nAre you sure you want to quit?", parent=self.root):
                self.running = False # Attempt to signal thread (basic)
                # Note: Daemon threads might not stop cleanly here. Consider more robust cancellation if needed.
                self.root.destroy()
            else:
                return # Don't close
        else:
            # Optionally save settings on close?
            # self.save_settings()
            self.root.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    # --- Optional: Tesseract Setup/Check ---
    # Uncomment and modify the path if Tesseract isn't in your system's PATH
    # tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # Example Windows Path
    # try:
    #      if os.path.exists(tesseract_path):
    #           pytesseract.pytesseract.tesseract_cmd = tesseract_path
    #      else:
    #           # Try finding Tesseract in PATH if specific path doesn't exist
    #           pass # pytesseract usually checks PATH by default

    #      # Verify Tesseract is accessible and list languages
    #      available_langs = pytesseract.get_languages(config='')
    #      print(f"Tesseract found. Available languages: {available_langs}")
    #      if not available_langs:
    #          print("Warning: Tesseract found, but no language data files seem to be available.")
    # except Exception as e:
    #      # Use tk messagebox if GUI is about to start, otherwise print
    #      msg = f"Tesseract OCR Error:\n{e}\n\nOCR functionality might not work correctly. Please ensure Tesseract is installed and configured."
    #      print(msg)
    #      try:
    #          root_temp = tk.Tk()
    #          root_temp.withdraw() # Hide temp window
    #          messagebox.showwarning("Tesseract Check", msg)
    #          root_temp.destroy()
    #      except tk.TclError:
    #          pass # Can't show messagebox if Tk isn't ready

    # --- Start Application ---
    root = tk.Tk()
    app = Application(root)
    root.mainloop()