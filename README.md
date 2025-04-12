# DeepPDF-Summarizer

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
2.Enter the directory where the project is located：
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
    python pdf-reader-text-image-version3.py
    ```

Make sure Tesseract-OCR is correctly installed and accessible on your system.
