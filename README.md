# My Resume Builder

A Python-based automated resume builder that compiles a Markdown-formatted CV into optimized HTML and print-ready PDF using Google Chrome headless, fully automated with GitHub Actions.

## Technology Stack

- **Python 3.11** (`resume.py`) — The core build script.
- **Python-Markdown** — Converts `resume.md` into standard HTML.
- **minify-html** — Compresses and optimizes the output HTML/CSS.
- **CSS** (`resume.css`) — Custom styling featuring the **Barlow** typeface from Google Fonts.
- **Google Chrome Headless** — Uses `--print-to-pdf` to export pixel-perfect PDFs.
- **GitHub Actions** (`.github/`) — Automated CI/CD pipeline to build and update your CV on every push.

## Prerequisites

To run this project locally, you need:

- Python ≥ 3.11
- Required Python packages:
  ```bash
  pip install markdown minify-html
  ```
- Google Chrome or Chromium (required for PDF output)

## Usage

1. **Edit your content**: Open `resume.md` and update your personal information, experience, and skills.
2. **Build locally**: Run the main script to generate your updated `resume.html` and `resume.pdf`:
   ```bash
   python resume.py
   ```
   * Use `--no-html` or `--no-pdf` if you want to skip a specific output format.
   * Use `--chrome-path=/path/to/chrome` if the script cannot find your Chrome executable.

## Automation with GitHub Actions

You do not need to build the PDF manually every time. When you push changes to GitHub:
1. The GitHub Actions workflow triggers automatically.
2. It sets up Python 3.11 and installs dependencies.
3. It builds the latest `resume.html` and `resume.pdf`.
4. The generated assets are automatically committed back to your repository or deployed.

## Customization

- **Styling**: Edit `resume.css` to change layouts, colors, or sizes. The project is pre-configured to use the professional **Barlow** font.
- **PDF Layout**: Modify rules under the `@media print` CSS selector to change how the PDF looks without affecting the web HTML version.
- **Page Margins**: Adjust the size and margins of the PDF page inside the `@page` CSS block.

