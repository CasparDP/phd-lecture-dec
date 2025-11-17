# This script converts PDF research papers into Quarto summaries using local Ollama.
# Workflow: PDF → Markdown (Docling) → LLM Summary (Ollama) → Quarto .qmd file
# Extracts: research idea, contribution, theory, hypothesis, design, results

import os
import sys
import json
import hashlib
import ollama
from pathlib import Path
from docling.document_converter import DocumentConverter
from typing import List, Optional
from datetime import datetime


def get_cache_dir() -> Path:
    """Get or create cache directory for extracted markdown."""
    repo_root = Path(__file__).parent.parent.parent
    cache_dir = repo_root / ".docling_cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_cache_key(pdf_path: Path) -> str:
    """Generate a cache key based on PDF filename and modification time."""
    stat_info = pdf_path.stat()
    cache_input = f"{pdf_path.name}:{stat_info.st_mtime}:{stat_info.st_size}"
    return hashlib.md5(cache_input.encode()).hexdigest()


def get_cached_markdown(pdf_path: Path) -> Optional[str]:
    """Load cached markdown if available and valid."""
    cache_dir = get_cache_dir()
    cache_key = get_cache_key(pdf_path)
    cache_file = cache_dir / f"{cache_key}.md"

    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                return f.read()
        except Exception as e:
            print(f"   ⚠️  Warning: Could not read cache: {e}")
    return None


def save_cached_markdown(pdf_path: Path, markdown: str) -> None:
    """Save markdown to cache."""
    cache_dir = get_cache_dir()
    cache_key = get_cache_key(pdf_path)
    cache_file = cache_dir / f"{cache_key}.md"

    try:
        with open(cache_file, "w") as f:
            f.write(markdown)
    except Exception as e:
        print(f"   ⚠️  Warning: Could not save cache: {e}")


def get_pdf_files(
    pdf_names: Optional[List[str]] = None,
) -> List[Path]:
    """
    Get PDF files to process from papers directory.

    Args:
        pdf_names: List of specific PDF filenames to process.
                  If None, process all PDFs in the directory.

    Returns:
        List of Path objects for PDF files to process.
    """
    # Use papers directory in repo root
    repo_root = Path(__file__).parent.parent.parent
    papers_dir = repo_root / "papers"

    if not papers_dir.exists():
        print(f"❌ Error: Papers directory not found at {papers_dir}")
        print("Please create the directory or check the path.")
        return []

    if pdf_names:
        # Process specific files
        pdf_files = []
        for name in pdf_names:
            pdf_path = papers_dir / name
            if pdf_path.exists() and pdf_path.suffix.lower() == ".pdf":
                pdf_files.append(pdf_path)
            else:
                print(f"⚠️  Warning: PDF not found or not a PDF file: {pdf_path}")
        return pdf_files
    else:
        # Process all PDFs in directory
        pdf_files = sorted(papers_dir.glob("*.pdf"))
        return pdf_files


def extract_markdown_from_pdf(pdf_path: Path) -> Optional[str]:
    """
    Extract markdown content from PDF using Docling with caching.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Markdown string or None if conversion fails.
    """
    # Check cache first
    cached = get_cached_markdown(pdf_path)
    if cached:
        print("   ✓ Using cached extraction")
        return cached

    # Extract if not cached
    print("   → Extracting from PDF (this may take a moment)...")
    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        markdown = result.document.export_to_markdown()

        # Save to cache
        save_cached_markdown(pdf_path, markdown)
        return markdown
    except Exception as e:
        print(f"   ❌ Error extracting from {pdf_path.name}: {e}")
        return None


def call_ollama_for_summary(markdown_content: str, model: str = "granite4:latest") -> Optional[str]:
    """
    Send markdown content to local Ollama and get structured summary.

    Args:
        markdown_content: The paper content in markdown format.
        model: Ollama model to use (default: granite4:latest).

    Returns:
        LLM response with summary or None if request fails.
    """

    system_prompt = """You are a research paper summarizer. Your job is to extract specific information from academic papers and present it in a structured format. Do not ask questions, do not add commentary, and do not mention that you read the paper. Simply provide the requested information."""

    user_prompt = f"""Extract the following information from this research paper. Provide ONLY the requested information with no additional commentary, questions, or meta-statements.

## Research Idea
[What is the core research question or idea?]

## Contribution
[What are the main contributions?]

## Theory
[What theoretical framework is used?]

## Hypothesis Development
[What hypotheses are developed?]

## Research Design
[What methodology and research design is used?]

## Results
[What are the key findings and results?]

---

PAPER CONTENT:
{markdown_content}

---

Now provide the summary following the exact structure above. Do not ask clarifying questions. Do not add statements like "I have read" or "I analyzed". Just provide the extracted information."""

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            stream=False,
            options={
                "temperature": 0.02,  # Lower temperature for more focused output
                "top_p": 0.9,
            }
        )
        return response["message"]["content"].strip()
    except Exception as e:
        print(f"   ❌ Error calling Ollama: {e}")
        print("   Please ensure Ollama is running: ollama serve")
        return None

def create_quarto_file(
    pdf_name: str, summary: str, output_dir: Path, model: str = "tralmis"
) -> Path:
    """
    Create a Quarto .qmd file with the summary.

    Args:
        pdf_name: Original PDF filename (for title).
        summary: The LLM-generated summary.
        output_dir: Directory to save the .qmd file.
        model: The model used to generate the summary.

    Returns:
        Path to the created .qmd file.
    """
    # Clean filename for title
    title = pdf_name.replace(".pdf", "").replace("_", " ").title()

    qmd_content = f"""---
title: "{title} - Research Summary"
date: "{datetime.now().strftime('%Y-%m-%d')}"
model: '{model}'
format: html
---

# Paper Summary

{summary}

---
Generated by Paper Summarizer using Ollama (Model: {model})
"""

    output_file = output_dir / f"{Path(pdf_name).stem}_summary.qmd"
    with open(output_file, "w") as f:
        f.write(qmd_content)

    return output_file


def process_paper(pdf_path: Path, output_base_dir: Path, model: str = "granite4:latest") -> bool:
    """
    Complete pipeline: PDF → Markdown → LLM Summary → Quarto file.

    Args:
        pdf_path: Path to the PDF file.
        output_base_dir: Base directory for output.
        model: Ollama model to use.

    Returns:
        True if successful, False otherwise.
    """
    # Create output directory
    pdf_stem = pdf_path.stem
    output_dir = output_base_dir / pdf_stem
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📄 Processing: {pdf_path.name}")

    # Step 1: Extract markdown from PDF
    print("   → Extracting content from PDF...")
    markdown = extract_markdown_from_pdf(pdf_path)
    if not markdown:
        return False

    # Step 2: Generate summary with Ollama
    print("   → Generating summary with Ollama...")
    summary = call_ollama_for_summary(markdown, model)
    if not summary:
        return False

    # Step 3: Create Quarto file
    print("   → Creating Quarto summary file...")
    qmd_file = create_quarto_file(pdf_path.name, summary, output_dir, model)
    print(f"   ✓ Summary saved to {qmd_file}")

    return True


def main():
    """
    Main function to process research papers.

    Usage:
        python report_to_docling.py                      # Process all PDFs
        python report_to_docling.py file1.pdf file2.pdf  # Process specific files
        python report_to_docling.py --model llama2       # Use specific model
    """
    # Parse command line arguments
    model = "granite4:latest"  # default model
    pdf_names = []

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--model" and i + 1 < len(args):
            model = args[i + 1]
        elif not arg.startswith("--"):
            pdf_names.append(arg)

    # Get PDF files to process
    pdf_files = get_pdf_files(pdf_names if pdf_names else None)

    if not pdf_files:
        print("❌ No PDF files found to process.")
        return

    print("=" * 70)
    print(f"📚 Paper Summarizer with Ollama")
    print("=" * 70)
    print(f"Model: {model}")
    print(f"Found {len(pdf_files)} paper(s) to process:")
    for i, pdf in enumerate(pdf_files, 1):
        print(f"  {i}. {pdf.name}")

    # Create output directory
    output_base_dir = Path("./paper_summaries")
    output_base_dir.mkdir(exist_ok=True)

    # Process each paper
    successful = 0
    failed = 0

    for pdf_path in pdf_files:
        if process_paper(pdf_path, output_base_dir, model):
            successful += 1
        else:
            failed += 1

    # Print summary
    print("\n" + "=" * 70)
    print("✅ Processing Complete")
    print("=" * 70)
    print(f"✓ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📁 Output directory: {output_base_dir.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
