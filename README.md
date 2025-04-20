# DeepPDF-Summarizer

This Python application provides a graphical user interface (GUI) to:
1.  Extract text content from PDF files.
2.  Perform Optical Character Recognition (OCR) on images embedded within PDFs.
3.  Generate concise summaries of the extracted text using the DeepSeek API.
4.  Handle large documents automatically by splitting text into manageable chunks for the API.

## Features

* **PDF Text Extraction**: Extracts text directly from PDF documents using PyMuPDF.
* **Integrated OCR**: Uses Tesseract OCR via `pytesseract` to extract text from images within PDFs.
    * Enable/Disable OCR functionality.
    * Select OCR language(s) (requires installed Tesseract language data).
    * Choose between OCRing **All Pages** or **Specific Pages/Ranges** (e.g., `0,1,5-8`).
* **AI Summarization**: Leverages the `deepseek-chat` model via the DeepSeek API to generate summaries.
* **Large Document Handling**: Automatically chunks text exceeding API limits, summarizes chunks individually, and then synthesizes a final summary.
* **Customizable Prompts**: Provide custom instructions to guide the summarization process.
* **User-Friendly GUI**: Built with Tkinter for ease of use.
* **Batch Processing**: Process all PDF files within a selected folder.
* **Output Management**:
    * Displays summaries in separate windows.
    * Option to save summaries to text files.
    * Option to copy summaries to the clipboard.
* **Configuration & Convenience**:
    * Saves settings (folder paths, instructions, OCR preferences) between sessions in `pdf_summarizer_config.json`. (API Key is *not* saved).
    * Remembers recently used folders.
    * Option to automatically open the processed PDF file.
    * Option to set a default save location for summaries.

## Requirements

- **Tesseract-OCR** (for OCR functionality)
  - **Windows**: Download the installer from [Tesseract Windows Installer](https://github.com/UB-Mannheim/tesseract/wiki).
  - **macOS**: Install using Homebrew: `brew install tesseract`.
  - **Linux**: Install using `sudo apt-get install tesseract-ocr`.

- **pytesseract**: `pip install pytesseract`
- **PyMuPDF**: `pip install PyMuPDF`
- **Pillow**: `pip install Pillow`
- **keyboard**: `pip install keyboard`
- **requests**: `pip install requests`
## How to Use

1. Clone this repository:
    ```bash
    git clone https://github.com/phoenix060505/DeepPDF-Summarizer.git
    ```
2. Enter the directory where the project is located：
    ```bash
    cd DeepPDF-Summarizer
    ```
3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4. Install Tesseract-OCR:
    - Follow the instructions above to install Tesseract-OCR based on your operating system.
  
5. Run the script:
    ```bash
    python pdf-reader-text-image-version5.py
    ```
    
6.  **Enter API Key**: In the "Main" tab, enter your **DeepSeek API Key**. This is required for summarization and is *not* saved between sessions for security. You can toggle visibility with the "Show" checkbox.

7.  **Select PDF Folder**: Click "Browse..." to choose the folder containing the PDF files you want to process. You can also use the "Recent" dropdown to select previously used folders.

8.  **Customize Instruction (Optional)**: Modify the text in the "Instruction:" box to guide the AI's summarization (e.g., "Provide a bullet-point summary focusing on financial results.").

9.  **Configure OCR Settings (Optional)**:
    * Check **"Enable OCR on Images"** if you need to extract text from images within the PDFs.
    * If OCR is enabled:
        * Check **"All Pages"** to attempt OCR on images found on every page.
        * **OR**, uncheck "All Pages" and enter specific page numbers or ranges in the **"Specific Pages..."** box. Remember pages are 0-indexed (0 is the first page). Examples: `0`, `0,1,5`, `5-8`, `0,2,5-8`.
        * Select the correct **"Language (Tesseract)"** from the dropdown. Ensure you have installed the corresponding language data for Tesseract (e.g., `eng` for English, `chi_sim` for Simplified Chinese, `eng+chi_sim` for both).

10.  **Start Processing**: Click the **"Start Processing"** button. The status bar and progress bar will show the progress. Processing time depends on the number/size of PDFs, OCR usage, and API response time.

11.  **View Summaries**: As each PDF is processed, a new window will pop up displaying the generated summary.
    * Click **"Save Summary"** to save the text to a file.
    * Click **"Copy to Clipboard"** to copy the text.
    * Click **"Close"** to close the summary window.

12.  **Settings Tab**:
    * Configure whether PDF files should be opened automatically after processing.
    * Set a default directory where the "Save Summary" dialog should start.
    * Click "Save Settings" to persist these options.

## Configuration File

* The application automatically creates and updates a file named `pdf_summarizer_config.json` in the same directory as the script.
* This file stores your settings like the last used folder, custom instruction, OCR preferences (language, pages setting, all pages flag), recent folders, and other UI settings.
* **Your DeepSeek API key is NEVER saved in this file.**

## Troubleshooting

* **Tesseract Not Found / OCR Errors**: Ensure Tesseract is correctly installed, its language data files are present, and it's either in your system PATH or the script is configured with the correct path to `tesseract.exe` (or equivalent). Check the console output when running the script for specific error messages from `pytesseract`.
* **API Errors**:
    * Verify your DeepSeek API key is correct and active.
    * Check your internet connection.
    * Check the DeepSeek API status page for outages.
    * Look for `HTTP Error` details in the console output (e.g., 401 Unauthorized, 429 Rate Limit Exceeded, 5xx Server Error).
    * Content filtering errors might occur based on DeepSeek's policies.
* **Slow Performance**: Summarizing many large PDFs, especially with OCR enabled on many pages, can take significant time. API response times also vary.
* **Incorrect OCR Results**: Ensure the correct language is selected in the dropdown and that the corresponding Tesseract language data is installed and functional. Image quality in the PDF also heavily affects OCR accuracy.

## License

This project is licensed under the MIT License - see the LICENSE.md file for details (if applicable).

