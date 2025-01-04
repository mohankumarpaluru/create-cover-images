# Blog OG Image Generator

<div style="text-align:center;">
<img src="https://github.com/mohankumarpaluru/blog-cover-generator/raw/refs/heads/main/public/assets/ai-image.jpg" alt="Blog Cover Generator Logo" height="300">
</div>

## Overview
Blog OG Image Generator is a Python-based project that creates visually appealing Open Graph (OG) images for your blog posts. It processes Markdown files, extracts the title using regular expressions, and generates a custom image using the Pillow library. Additionally, GitHub Actions can automate the generation process whenever new Markdown files are added or updated in the repository.

---

## Features
- Extracts blog titles from Markdown files using Regex.
- Creates custom OG images with a modern design using Pillow.
- Automates image generation with GitHub Actions.
- Easily customizable templates for consistent branding.

---

## Requirements

### Python Dependencies
- Python 3.8+
- `Pillow` (for image manipulation)
- `re` (for regex title extraction)

### Optional
- A GitHub repository with GitHub Actions enabled.

---

## Installation
1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd blog-og-image-generator
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Usage
1. Add your Markdown files to the designated directory (e.g., `markdown_files/`).
2. Run the script to generate OG images:
   ```bash
   python generate_og_image.py
   ```
3. Check the output folder (e.g., `output_images/`) for the generated images.

---

## Automating with GitHub Actions
1. Add the provided `.github/workflows/generate_og_image.yml` to your repository.
2. Commit and push your changes.
3. The GitHub Actions workflow will automatically generate OG images when Markdown files are added or updated.

---

## Customization
- Modify the `template.png` file to customize the OG image design.
- Update the `generate_og_image.py` script to adjust font styles, colors, or layout.
