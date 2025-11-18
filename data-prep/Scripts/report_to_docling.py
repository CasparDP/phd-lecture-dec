#!/usr/bin/env python3
"""
Academic PDF Summarizer using Granite4 + Ollama

Robust pipeline for PDF → text extraction → chunking → map-reduce summarization.

Features:
- Modular pipeline with clear separation of concerns
- Robust PDF extraction with fallback methods (docling → PyMuPDF)
- Token-aware overlapping chunking
- Multi-level caching (text, chunks, map outputs)
- Deterministic behavior (temperature=0)
- Progress logging
- CLI interface with argparse
"""

import os
import sys
import json
import hashlib
import logging
import argparse
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import time

# Third-party imports
import ollama
import tiktoken

# Docling imports (primary extraction)
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logging.warning("Docling not available. Using fallback extraction only.")

# PyMuPDF imports (fallback extraction)
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logging.warning("PyMuPDF not available. Install with: pip install pymupdf")

# ============================================================================
# CONFIGURATION
# ============================================================================

# Default model configuration
DEFAULT_MODEL = "granite4:latest"
DEFAULT_CHUNK_SIZE = 2000  # tokens
DEFAULT_CHUNK_OVERLAP = 200  # tokens
TEMPERATURE = 0  # Deterministic behavior

# Cache directory
CACHE_DIR_NAME = ".docling_cache"

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

def load_prompt_template(filename: str, default: str) -> str:
    """Load prompt template from file with fallback to default."""
    try:
        script_dir = Path(__file__).parent
        prompt_path = script_dir / filename
        if prompt_path.exists():
            with open(prompt_path, "r") as f:
                return f.read()
    except Exception as e:
        logger.warning(f"Could not load {filename}: {e}")
    return default


MAP_PROMPT_TEMPLATE = load_prompt_template(
    "map_prompt.txt",
    """You are an expert AI research assistant. Your task is to process a single chunk of an academic paper.

Read the text chunk provided below and extract ONLY the following key information. Present your output in this exact format, with headings. If a section is not present in the chunk, write "N/A".

Do not write a "summary" in prose. Your job is to extract and list.

1.  **Main Claims:** (What are the key arguments, findings, or hypotheses stated in this section?)
2.  **Key Methodology:** (What methods, techniques, or models are described? If N/A, write "N/A".)
3.  **Core Evidence/Results:** (What data, statistics, or evidence is presented to support the claims? If N/A, write "N/A".)
4.  **Important Context/Definitions:** (Any key definitions or context needed to understand this chunk? If N/A, write "N/A".)

Here is the text chunk:
---
{text_chunk}
---"""
)

REDUCE_PROMPT_TEMPLATE = load_prompt_template(
    "reduce_prompt.txt",
    """You are an expert AI academic writer. You have been given a series of structured notes, each extracted from a consecutive chunk of a single academic paper.

Your task is to synthesize these notes into a single, high-quality, and coherent summary of the *entire paper*.

The notes are separated by "---". You must read and understand all of them to build the full picture.

The final summary should be a single, well-written paragraph that covers:
1.  The main research question or objective.
2.  The methodology used.
3.  The key findings or results.
4.  The final conclusion and its implications.

Do not just list the points. Weave them together into a professional, academic summary.

Here are the structured notes:
---
{synthesis_document}
---

Write the final, synthesized summary below:"""
)


# ============================================================================
# HELPER FUNCTIONS: Caching, Token Counting
# ============================================================================

def get_cache_dir() -> Path:
    """Get or create cache directory for intermediate outputs."""
    repo_root = Path(__file__).parent.parent.parent
    cache_dir = repo_root / CACHE_DIR_NAME
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_cache_path(pdf_path: Path, suffix: str) -> Path:
    """
    Generate cache file path for a PDF and cache type.

    Args:
        pdf_path: Path to the PDF file
        suffix: Cache type suffix (e.g., 'text', 'chunks', 'map')

    Returns:
        Path to cache file
    """
    cache_dir = get_cache_dir()
    # Use PDF stem + suffix for cache filename
    cache_filename = f"{pdf_path.stem}.{suffix}.json"
    return cache_dir / cache_filename


def save_cache(obj: Any, filename: str) -> None:
    """
    Write JSON cache to disk.

    Args:
        obj: Object to cache (must be JSON serializable)
        filename: Cache filename (full path)
    """
    try:
        cache_path = Path(filename) if not isinstance(filename, Path) else filename
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        logger.debug(f"Cache saved: {cache_path.name}")
    except Exception as e:
        logger.warning(f"Could not save cache to {filename}: {e}")


def load_cache(filename: str) -> Optional[Any]:
    """
    Load cache if available.

    Args:
        filename: Cache filename (full path)

    Returns:
        Cached object or None if not available
    """
    try:
        cache_path = Path(filename) if not isinstance(filename, Path) else filename
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Cache loaded: {cache_path.name}")
            return data
    except Exception as e:
        logger.warning(f"Could not load cache from {filename}: {e}")
    return None


def count_tokens(text: str) -> int:
    """
    Estimate token count using tiktoken (cl100k_base encoding).

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough approximation (1 token ≈ 4 characters)
        return len(text) // 4


# ============================================================================
# CORE PIPELINE FUNCTIONS
# ============================================================================

def extract_text_from_pdf(path: str) -> str:
    """
    Extract clean text from PDF using docling, fallback to PyMuPDF.

    Primary method: Docling (preserves structure, better for academic papers)
    Fallback method: PyMuPDF (more robust for difficult PDFs)

    Args:
        path: Path to PDF file

    Returns:
        Extracted text content

    Raises:
        Exception: If both extraction methods fail
    """
    logger.info("Extracting text from PDF...")

    pdf_path = Path(path)

    # Try docling first (primary method)
    if DOCLING_AVAILABLE:
        try:
            logger.debug("Attempting extraction with Docling...")
            converter = DocumentConverter()
            result = converter.convert(str(pdf_path))
            text = result.document.export_to_markdown()

            if text and len(text.strip()) > 100:  # Sanity check
                logger.info("✓ Text extracted successfully (Docling)")
                return text
            else:
                logger.warning("Docling extraction returned insufficient text")
        except Exception as e:
            logger.warning(f"Docling extraction failed: {e}")

    # Fallback to PyMuPDF
    if PYMUPDF_AVAILABLE:
        try:
            logger.debug("Attempting extraction with PyMuPDF...")
            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text_parts.append(page.get_text())

            doc.close()
            text = "\n\n".join(text_parts)

            if text and len(text.strip()) > 100:  # Sanity check
                logger.info("✓ Text extracted successfully (PyMuPDF fallback)")
                return text
            else:
                logger.warning("PyMuPDF extraction returned insufficient text")
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}")

    # Both methods failed
    raise Exception(
        "PDF extraction failed with all methods. "
        "Please ensure docling or PyMuPDF is installed."
    )


def clean_extracted_text(text: str) -> str:
    """
    Remove headers, footers, references, page numbers, and empty lines.

    This function cleans common artifacts from academic PDFs:
    - Page numbers
    - Headers and footers
    - Reference sections
    - Excessive whitespace
    - LaTeX equation artifacts

    Args:
        text: Raw extracted text

    Returns:
        Cleaned text
    """
    logger.debug("Cleaning extracted text...")

    # Remove page numbers (common patterns)
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
    text = re.sub(r'\n\s*Page \d+\s*\n', '\n', text, flags=re.IGNORECASE)

    # Remove common header/footer patterns
    text = re.sub(r'\n\s*\d+\s+[A-Z][a-z]+\s+et\s+al\.\s*\n', '\n', text)

    # Remove LaTeX artifacts
    text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', text)
    text = re.sub(r'\$[^$]+\$', '[equation]', text)

    # Try to remove references section (heuristic)
    # Look for common reference section headers
    ref_patterns = [
        r'\n\s*(References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*\n',
        r'\n\s*\d+\.\s+References\s*\n'
    ]

    for pattern in ref_patterns:
        match = re.search(pattern, text)
        if match:
            # Keep everything before the references section
            text = text[:match.start()]
            logger.debug("Removed references section")
            break

    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 consecutive newlines
    text = re.sub(r' {2,}', ' ', text)  # Max 1 space
    text = text.strip()

    logger.debug("✓ Text cleaned")
    return text


def chunk_text(text: str, max_tokens: int = 2000, overlap: int = 200) -> List[str]:
    """
    Token-aware overlapping chunking suitable for Granite4.

    Strategy:
    - Split on paragraph boundaries when possible
    - Ensure chunks stay within token limits
    - Add overlap for context continuity
    - Never cut mid-sentence unless unavoidable

    Args:
        text: Input text to chunk
        max_tokens: Maximum tokens per chunk
        overlap: Overlap size in tokens (for continuity)

    Returns:
        List of text chunks
    """
    logger.info(f"Creating chunks (max: {max_tokens} tokens, overlap: {overlap} tokens)...")

    # Split into sentences (basic approach)
    # More sophisticated: use paragraph boundaries
    paragraphs = text.split('\n\n')

    chunks = []
    current_chunk = ""
    current_tokens = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = count_tokens(para)

        # If single paragraph exceeds max, split it further
        if para_tokens > max_tokens:
            # Split by sentences
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sent in sentences:
                sent_tokens = count_tokens(sent)

                if current_tokens + sent_tokens > max_tokens and current_chunk:
                    # Save current chunk
                    chunks.append(current_chunk.strip())

                    # Start new chunk with overlap
                    # Take last part of previous chunk as overlap
                    overlap_text = get_overlap_text(current_chunk, overlap)
                    current_chunk = overlap_text + " " + sent
                    current_tokens = count_tokens(current_chunk)
                else:
                    current_chunk += " " + sent
                    current_tokens += sent_tokens
        else:
            # Normal paragraph processing
            if current_tokens + para_tokens > max_tokens and current_chunk:
                # Save current chunk
                chunks.append(current_chunk.strip())

                # Start new chunk with overlap
                overlap_text = get_overlap_text(current_chunk, overlap)
                current_chunk = overlap_text + "\n\n" + para
                current_tokens = count_tokens(current_chunk)
            else:
                current_chunk += "\n\n" + para if current_chunk else para
                current_tokens += para_tokens

    # Add final chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    logger.info(f"✓ Created {len(chunks)} chunks")

    # Log chunk details
    for i, chunk in enumerate(chunks, 1):
        tokens = count_tokens(chunk)
        logger.debug(f"  Chunk {i}: {tokens} tokens, {len(chunk)} chars")

    return chunks


def get_overlap_text(text: str, overlap_tokens: int) -> str:
    """
    Extract the last N tokens worth of text for overlap.

    Args:
        text: Source text
        overlap_tokens: Number of tokens to extract

    Returns:
        Overlap text (approximately overlap_tokens in length)
    """
    # Simple approximation: take last N*4 characters (1 token ≈ 4 chars)
    approx_chars = overlap_tokens * 4

    if len(text) <= approx_chars:
        return text

    # Try to break at sentence boundary
    overlap_text = text[-approx_chars:]

    # Find first sentence start
    match = re.search(r'[.!?]\s+', overlap_text)
    if match:
        overlap_text = overlap_text[match.end():]

    return overlap_text


def run_map_step(chunk: str, model: str = "granite4:latest") -> Dict[str, Any]:
    """
    Call Ollama with the map prompt and return structured output.

    Processes a single chunk and extracts key information.
    Uses temperature=0 for deterministic output.

    Args:
        chunk: Text chunk to process
        model: Ollama model name

    Returns:
        Dictionary with extracted information
    """
    prompt = MAP_PROMPT_TEMPLATE.format(text_chunk=chunk)

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": TEMPERATURE},
                stream=False
            )

            content = response["message"]["content"].strip()

            # Return structured output
            return {
                "content": content,
                "model": model,
                "tokens": count_tokens(content)
            }

        except Exception as e:
            logger.warning(f"Map step attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logger.error(f"Map step failed after {max_retries} attempts")
                return {
                    "content": f"[ERROR: Failed to process chunk: {e}]",
                    "model": model,
                    "tokens": 0,
                    "error": str(e)
                }


def run_reduce_step(mapped_chunks: List[Dict[str, Any]], model: str = "granite4:latest") -> str:
    """
    Combine mapped outputs into final summary via reduce prompt.

    Synthesizes information from all chunk summaries into a coherent whole.
    Uses temperature=0 for deterministic output.

    Args:
        mapped_chunks: List of map step outputs
        model: Ollama model name

    Returns:
        Final synthesized summary
    """
    logger.info("Running reduce step...")

    # Combine all mapped content
    synthesis_parts = []
    for i, chunk_data in enumerate(mapped_chunks, 1):
        content = chunk_data.get("content", "")
        synthesis_parts.append(f"[Chunk {i}]\n{content}")

    synthesis_document = "\n\n---\n\n".join(synthesis_parts)

    prompt = REDUCE_PROMPT_TEMPLATE.format(synthesis_document=synthesis_document)

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": TEMPERATURE},
                stream=False
            )

            summary = response["message"]["content"].strip()
            logger.info("✓ Reduce step complete")
            return summary

        except Exception as e:
            logger.warning(f"Reduce step attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logger.error(f"Reduce step failed after {max_retries} attempts")
                return f"[ERROR: Failed to synthesize summary: {e}]"


def summarize_pdf(path: str, model: str = "granite4:latest", force: bool = False) -> str:
    """
    High-level function calling extract → chunk → map → reduce.

    Complete pipeline with caching at each stage:
    1. Extract text from PDF (cached)
    2. Clean text (cached)
    3. Chunk text (cached)
    4. Map step - process each chunk (cached)
    5. Reduce step - synthesize final summary

    Args:
        path: Path to PDF file
        model: Ollama model name
        force: If True, ignore cache and reprocess

    Returns:
        Final summary text
    """
    pdf_path = Path(path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    logger.info(f"\n{'='*70}")
    logger.info(f"Processing: {pdf_path.name}")
    logger.info(f"{'='*70}")

    # Step 1: Extract text (with cache)
    text_cache_path = get_cache_path(pdf_path, "text")

    if not force and (cached_text := load_cache(text_cache_path)):
        logger.info("✓ Using cached extracted text")
        extracted_text = cached_text["text"]
    else:
        extracted_text = extract_text_from_pdf(str(pdf_path))
        save_cache({"text": extracted_text, "timestamp": datetime.now().isoformat()}, text_cache_path)

    # Step 2: Clean text (with cache)
    cleaned_cache_path = get_cache_path(pdf_path, "cleaned")

    if not force and (cached_cleaned := load_cache(cleaned_cache_path)):
        logger.info("✓ Using cached cleaned text")
        cleaned_text = cached_cleaned["text"]
    else:
        cleaned_text = clean_extracted_text(extracted_text)
        save_cache({"text": cleaned_text, "timestamp": datetime.now().isoformat()}, cleaned_cache_path)

    # Step 3: Chunk text (with cache)
    chunks_cache_path = get_cache_path(pdf_path, "chunks")

    if not force and (cached_chunks := load_cache(chunks_cache_path)):
        logger.info("✓ Using cached chunks")
        chunks = cached_chunks["chunks"]
        logger.info(f"Loaded {len(chunks)} chunks from cache")
    else:
        chunks = chunk_text(cleaned_text, max_tokens=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP)
        save_cache({
            "chunks": chunks,
            "count": len(chunks),
            "timestamp": datetime.now().isoformat()
        }, chunks_cache_path)

    # Step 4: Map step - process each chunk (with cache)
    map_cache_path = get_cache_path(pdf_path, "map")

    if not force and (cached_map := load_cache(map_cache_path)):
        logger.info("✓ Using cached map outputs")
        mapped_outputs = cached_map["mapped_outputs"]
    else:
        logger.info(f"Running map step on {len(chunks)} chunks...")
        mapped_outputs = []

        for i, chunk in enumerate(chunks, 1):
            logger.info(f"  Processing chunk {i}/{len(chunks)}...")
            result = run_map_step(chunk, model=model)
            mapped_outputs.append(result)

        save_cache({
            "mapped_outputs": mapped_outputs,
            "model": model,
            "timestamp": datetime.now().isoformat()
        }, map_cache_path)

        logger.info("✓ Map step complete")

    # Step 5: Reduce step - synthesize final summary (always fresh)
    logger.info("Generating final summary...")
    final_summary = run_reduce_step(mapped_outputs, model=model)

    logger.info("✓ Summary complete")
    logger.info(f"{'='*70}\n")

    return final_summary


def chunk_markdown(doc_object: object, chunk_size: int = 1000) -> List[Dict]:
    """
    Split Document into semantic chunks using HybridChunker.

    Args:
        doc_object: The DoclingDocument object to chunk.
        chunk_size: Target size for each chunk in tokens (default: 1000).

    Returns:
        List of chunk dictionaries with metadata and text content.
    """
    print(f"\n   → Chunking document (target: {chunk_size} tokens per chunk)...")

    try:
        # Initialize the chunker
        chunker = HybridChunker(max_tokens=chunk_size)

        # Chunk the document
        chunks = chunker.chunk(doc_object)

        # Convert chunks to list with metadata
        chunk_list = []
        for idx, chunk in enumerate(chunks, 1):
            # Extract text from chunk
            chunk_text = chunk.text
            chunk_tokens = count_tokens(chunk_text)

            chunk_dict = {
                "id": idx,
                "text": chunk_text,
                "tokens": chunk_tokens,
            }
            chunk_list.append(chunk_dict)

            # Debug print
            print(f"      Chunk {idx}: {chunk_tokens} tokens ({len(chunk_text)} chars)")

        print(f"   ✓ Created {len(chunk_list)} chunks")
        return chunk_list
    except Exception as e:
        print(f"   ❌ Error chunking document: {e}")
        return []


def summarize_chunk(chunk: Dict, model: str = "granite4:latest") -> str:
    """
    Summarize a single chunk with 5-10 sentences, including position metadata.

    Args:
        chunk: Dictionary with 'id', 'text', and 'tokens' keys.
        model: Ollama model to use.

    Returns:
        Summary string with chunk reference.
    """
    system_prompt = """You are a concise research analyst. Summarize the provided text section in 5-10 sentences.
Focus on the key insights and main points. Be specific and factual."""

    user_prompt = f"""Summarize this section in 5-10 sentences:

{chunk['text']}

Summary:"""

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            stream=False,
            options={
                "temperature": 0.1,
                "top_p": 0.9
            }
        )
        summary_text = response["message"]["content"].strip()
        # Add chunk metadata to the summary
        return f"[Chunk {chunk['id']}] {summary_text}"
    except Exception as e:
        print(f"   ❌ Error summarizing chunk {chunk['id']}: {e}")
        return f"[Chunk {chunk['id']}] Error: Could not summarize."


def combine_chunk_summaries(chunk_summaries: List[str]) -> str:
    """
    Combine individual chunk summaries into a single meta-summary document.

    Args:
        chunk_summaries: List of chunk summary strings.

    Returns:
        Combined summaries with dividers and metadata.
    """
    print(f"\n   → Combining {len(chunk_summaries)} chunk summaries...")

    combined = "# Document Summary (from Section Summaries)\n\n"
    combined += "This is a hierarchical summary of document sections:\n\n"

    for i, summary in enumerate(chunk_summaries, 1):
        combined += f"{summary}\n\n"
        combined += f"{'---'}\n\n"

    return combined


def should_skip_chunking(markdown_content: str, threshold_tokens: int = 4000) -> bool:
    """
    Determine if document is small enough to skip chunking.

    Args:
        markdown_content: The markdown text.
        threshold_tokens: Token count threshold (default: 4000).

    Returns:
        True if document should skip chunking, False otherwise.
    """
    token_count = count_tokens(markdown_content)
    if token_count < threshold_tokens:
        print(f"   → Document is small ({token_count} tokens < {threshold_tokens} threshold)")
        print(f"   → Skipping chunking and sending directly to final summary")
        return True
    return False


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


def extract_document_from_pdf(pdf_path: Path) -> Optional[object]:
    """
    Extract Document object from PDF using Docling (for chunking).
    Uses the cached markdown as a fallback indicator, but always converts fresh.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        DoclingDocument object or None if conversion fails.
    """
    print("   → Extracting document structure from PDF (for chunking)...")
    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        return result.document
    except Exception as e:
        print(f"   ❌ Error extracting document from {pdf_path.name}: {e}")
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

    system_prompt = """You are an expert research analyst for academic finance and economics papers. Your task is to read markdown input and extract the requested fields for Quarto notes. Follow these rules:
- Use concise, declarative sentences. No questions, chit-chat, or meta commentary.
- If a section is missing evidence, reply with "Not specified" for that section.
- Keep each section under three sentences and retain any inline citations found in the source.
- Never mention that you read or analyzed the paper; just provide the information."""

    user_prompt = f"""Summarize the paper content below using the exact markdown template. Replace the placeholder guidance with factual content. If the paper omits a section, write "Not specified". Do not add extra headings, intro text, or conclusions.

## Research Idea
[ A brief summary of the main research question or idea explored in the paper. What is the core problem being addressed? What gap in the literature does it aim to fill? ]

## Contribution
[ A concise description of the paper's key contributions to the field. What new insights, methods, or findings does it offer? How does it advance existing knowledge? ]
## Theory
[ A summary of the theoretical framework or models used in the paper. What theories underpin the research? How do they inform the hypotheses or research questions? ]

## Hypothesis Development
[ An outline of the hypotheses proposed in the paper. What predictions are made based on the theory? How are these hypotheses justified? ]
## Research Design
[ A description of the research design and methodology. What data sources, sample, and empirical methods are used to test the hypotheses? ]

## Results
[ A summary of the main findings and results of the study. What were the key outcomes? Were the hypotheses supported? Include any significant statistical results. ]

---

PAPER CONTENT:
{markdown_content}

---"""

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
                "top_p": 0.9
                #"num_ctx": 20000,  # Adjust context length as needed
            }
        )
        return response["message"]["content"].strip()
    except Exception as e:
        print(f"   ❌ Error calling Ollama: {e}")
        print("   Please ensure Ollama is running: ollama serve")
        return None


def call_orchestrator_sync(markdown_content: str) -> Optional[str]:
    """
    Call the orchestrator agent for map-reduce summarization.

    Args:
        markdown_content: The paper content in markdown format.

    Returns:
        Final synthesized summary from map-reduce pipeline or None if fails.
    """
    try:
        orchestrator = OrchestratorAgent()
        summary = orchestrator.run(markdown_content)
        return summary
    except Exception as e:
        print(f"   ❌ Error in orchestrator call: {e}")
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
format: html
---

# Paper Summary

{summary}

:::{{.callout-note}}
# AI Generated Summary
Generated by Paper Summarizer using Ollama (Model: {model})
:::
"""

    output_file = output_dir / f"{Path(pdf_name).stem}_summary.qmd"
    with open(output_file, "w") as f:
        f.write(qmd_content)

    return output_file


def process_paper(pdf_path: Path, output_base_dir: Path, model: str = "granite4:latest", use_map_reduce: bool = False) -> bool:
    """
    Complete pipeline: PDF → Markdown → [Optional Map-Reduce] → Final Summary → Quarto file.

    Can use either:
    - Traditional approach: Full markdown → LLM summary
    - Map-Reduce approach: Split → Process chunks in parallel → Synthesize

    Args:
        pdf_path: Path to the PDF file.
        output_base_dir: Base directory for output.
        model: Ollama model to use (for traditional approach).
        use_map_reduce: If True, use map-reduce orchestrator; otherwise use traditional approach.

    Returns:
        True if successful, False otherwise.
    """
    # Create output directory
    pdf_stem = pdf_path.stem
    output_dir = output_base_dir / pdf_stem
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📄 Processing: {pdf_path.name}")
    approach = "Map-Reduce" if use_map_reduce else "Traditional"
    print(f"   Approach: {approach}")

    # Step 1: Extract markdown from PDF (cached)
    print("   → Extracting content from PDF...")
    markdown = extract_markdown_from_pdf(pdf_path)
    if not markdown:
        return False

    # Step 2: Generate summary using selected approach
    if use_map_reduce:
        print("   → Using Map-Reduce orchestrator for summarization...")
        summary = call_orchestrator_sync(markdown)
    else:
        print("   → Analyzing document size...")
        use_chunking = not should_skip_chunking(markdown, threshold_tokens=8000)

        if use_chunking:
            # Extract document for chunking
            doc = extract_document_from_pdf(pdf_path)
            if not doc:
                print("   ⚠️  Could not extract document structure, falling back to direct summarization...")
                input_for_final_summary = markdown
            else:
                # Chunk the document
                chunks = chunk_markdown(doc, chunk_size=3000)

                if not chunks:
                    print("   ⚠️  Chunking failed, using full document for summary...")
                    input_for_final_summary = markdown
                else:
                    # Summarize each chunk
                    print(f"\n   → Summarizing {len(chunks)} chunks individually...")
                    chunk_summaries = []
                    for i, chunk in enumerate(chunks, 1):
                        print(f"      [{i}/{len(chunks)}] Summarizing chunk {chunk['id']}...")
                        chunk_summary = summarize_chunk(chunk, model)
                        chunk_summaries.append(chunk_summary)

                    # Combine chunk summaries
                    input_for_final_summary = combine_chunk_summaries(chunk_summaries)
        else:
            # Skip chunking for small documents
            input_for_final_summary = markdown

        # Generate final structured summary with Ollama
        print("   → Generating final structured summary with Ollama...")
        summary = call_ollama_for_summary(input_for_final_summary, model)

    if not summary:
        return False

    # Step 3: Create Quarto file
    print("   → Creating Quarto summary file...")
    qmd_file = create_quarto_file(pdf_path.name, summary, output_dir, model)
    print(f"   ✓ Summary saved to {qmd_file}")

    return True


# ============================================================================
# CLI AND MAIN FUNCTION
# ============================================================================

def create_output_file(summary: str, pdf_path: Path, output_path: Optional[Path] = None, format: str = "md") -> Path:
    """
    Write summary to output file.

    Args:
        summary: Summary text
        pdf_path: Original PDF path
        output_path: Optional output path (default: same dir as PDF)
        format: Output format ('md' or 'txt')

    Returns:
        Path to created output file
    """
    if output_path is None:
        output_path = pdf_path.parent / f"{pdf_path.stem}_summary.{format}"

    if format == "md":
        content = f"""# Summary: {pdf_path.stem}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Source:** {pdf_path.name}

---

{summary}

---

*Generated by Academic PDF Summarizer using Granite4 + Ollama*
"""
    else:
        content = f"""Summary: {pdf_path.stem}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source: {pdf_path.name}

{'='*70}

{summary}

{'='*70}

Generated by Academic PDF Summarizer using Granite4 + Ollama
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"✓ Summary saved to: {output_path}")
    return output_path


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Academic PDF Summarizer using Granite4 + Ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --file paper.pdf
  %(prog)s --file paper.pdf --model granite4:latest
  %(prog)s --file paper.pdf --force --export summary.md
  %(prog)s --file paper.pdf --export --format txt
        """
    )

    parser.add_argument(
        '--file',
        type=str,
        required=True,
        help='Path to PDF file to summarize (required)'
    )

    parser.add_argument(
        '--model',
        type=str,
        default=DEFAULT_MODEL,
        help=f'Ollama model to use (default: {DEFAULT_MODEL})'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Ignore cache and reprocess from scratch'
    )

    parser.add_argument(
        '--export',
        type=str,
        nargs='?',
        const='auto',
        help='Export summary to file (optional path, default: <pdf_name>_summary.md)'
    )

    parser.add_argument(
        '--format',
        type=str,
        choices=['md', 'txt'],
        default='md',
        help='Output format for exported file (default: md)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='Academic PDF Summarizer v2.0'
    )

    return parser.parse_args()


def main():
    """
    Main CLI entry point.

    Usage:
        python report_to_docling.py --file paper.pdf
        python report_to_docling.py --file paper.pdf --model granite4:latest --force
        python report_to_docling.py --file paper.pdf --export summary.md
    """
    args = parse_arguments()

    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Print header
    logger.info("\n" + "="*70)
    logger.info("Academic PDF Summarizer - Granite4 + Ollama")
    logger.info("="*70)
    logger.info(f"Model: {args.model}")
    logger.info(f"Cache: {'Disabled (--force)' if args.force else 'Enabled'}")
    logger.info("="*70 + "\n")

    try:
        # Run summarization pipeline
        summary = summarize_pdf(args.file, model=args.model, force=args.force)

        # Print summary to terminal
        logger.info("\n" + "="*70)
        logger.info("SUMMARY")
        logger.info("="*70 + "\n")
        print(summary)
        logger.info("\n" + "="*70 + "\n")

        # Export if requested
        if args.export:
            pdf_path = Path(args.file)

            if args.export == 'auto':
                output_path = None  # Use default
            else:
                output_path = Path(args.export)

            create_output_file(summary, pdf_path, output_path, format=args.format)

        logger.info("✓ Processing complete!\n")
        return 0

    except FileNotFoundError as e:
        logger.error(f"\n❌ Error: {e}\n")
        return 1
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(main())
