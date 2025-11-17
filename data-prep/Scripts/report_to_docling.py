# This script converts PDF research papers into Quarto summaries using local Ollama.
# Workflow: PDF → Markdown (Docling) → LLM Summary (Ollama) → Quarto .qmd file
# Extracts: research idea, contribution, theory, hypothesis, design, results
# Enhanced with agentic Map-Reduce approach for large documents

import os
import sys
import json
import hashlib
import ollama
from pathlib import Path
from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import tiktoken  # For token counting

# ============================================================================
# CONFIGURATION & PROMPTS FOR MAP-REDUCE AGENTS
# ============================================================================

OLLAMA_MODEL = "granite4:latest"

# Load prompt templates with fallback defaults
try:
    script_dir = Path(__file__).parent
    with open(script_dir / "map_prompt.txt", "r") as f:
        MAP_PROMPT_TEMPLATE = f.read()
except FileNotFoundError:
    MAP_PROMPT_TEMPLATE = """You are an expert AI research assistant. Your task is to process a single chunk of an academic paper.

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

try:
    script_dir = Path(__file__).parent
    with open(script_dir / "reduce_prompt.txt", "r") as f:
        REDUCE_PROMPT_TEMPLATE = f.read()
except FileNotFoundError:
    REDUCE_PROMPT_TEMPLATE = """You are an expert AI academic writer. You have been given a series of structured notes, each extracted from a consecutive chunk of a single academic paper.

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


# ============================================================================
# AGENTIC MAP-REDUCE CLASSES
# ============================================================================

class TextSplitterAgent:
    """Intelligently splits text using a paragraph-based approach."""

    def run(self, full_text: str, chunk_size_target: int = 4000) -> List[str]:
        """
        Split text into chunks based on paragraph boundaries.

        Args:
            full_text: The complete text to split.
            chunk_size_target: Target size for each chunk in characters.

        Returns:
            List of text chunks.
        """
        print("   → TextSplitterAgent: Splitting document into chunks...")

        paragraphs = full_text.split("\n\n")
        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            test_chunk = current_chunk + paragraph + "\n\n"
            if len(test_chunk) > chunk_size_target and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
            else:
                current_chunk = test_chunk

        if current_chunk:
            chunks.append(current_chunk.strip())

        print(f"   ✓ TextSplitterAgent: Created {len(chunks)} chunks")
        return chunks


class MapAgent:
    """Summarizes a single chunk of text."""

    def run(self, text_chunk: str) -> str:
        """
        Process a single chunk with the LLM.

        Args:
            text_chunk: The text chunk to process.

        Returns:
            LLM response for the chunk.
        """
        print(f"   → MapAgent: Processing chunk (first 50 chars: {text_chunk[:50]}...)")

        formatted_prompt = MAP_PROMPT_TEMPLATE.format(text_chunk=text_chunk)
        response = self._call_ollama(formatted_prompt)

        print(f"   ✓ MapAgent: Finished processing chunk")
        return response

    def _call_ollama(self, prompt: str) -> str:
        """
        Call Ollama locally using the ollama Python library.

        Args:
            prompt: The prompt to send.

        Returns:
            Response from Ollama or error message.
        """
        try:
            response = ollama.generate(model=OLLAMA_MODEL, prompt=prompt, stream=False)
            return response.get("response", "").strip()
        except ollama.ResponseError as e:
            print(f"   ❌ MapAgent._call_ollama error: {e.error}")
            return f"Error: {str(e)}"
        except Exception as e:
            print(f"   ❌ MapAgent._call_ollama error: {e}")
            return f"Error: {str(e)}"


class ReduceAgent:
    """Synthesizes all chunk summaries into a final summary."""

    def run(self, synthesis_document: str) -> str:
        """
        Synthesize chunk summaries into final summary.

        Args:
            synthesis_document: Combined chunk summaries.

        Returns:
            Final synthesized summary.
        """
        print("   → ReduceAgent: Synthesizing chunk summaries...")

        formatted_prompt = REDUCE_PROMPT_TEMPLATE.format(
            synthesis_document=synthesis_document
        )
        response = self._call_ollama(formatted_prompt)

        print("   ✓ ReduceAgent: Finished synthesizing")
        return response

    def _call_ollama(self, prompt: str) -> str:
        """
        Call Ollama locally using the ollama Python library.

        Args:
            prompt: The prompt to send.

        Returns:
            Response from Ollama or error message.
        """
        try:
            response = ollama.generate(model=OLLAMA_MODEL, prompt=prompt, stream=False)
            return response.get("response", "").strip()
        except ollama.ResponseError as e:
            print(f"   ❌ ReduceAgent._call_ollama error: {e.error}")
            return f"Error: {str(e)}"
        except Exception as e:
            print(f"   ❌ ReduceAgent._call_ollama error: {e}")
            return f"Error: {str(e)}"


class OrchestratorAgent:
    """Manages the full Map-Reduce workflow."""

    def __init__(self):
        """Initialize orchestrator with agent instances."""
        self.splitter = TextSplitterAgent()
        self.mapper = MapAgent()
        self.reducer = ReduceAgent()

    def run(self, full_text: str) -> str:
        """
        Execute the complete Map-Reduce pipeline.

        Args:
            full_text: The complete document text.

        Returns:
            Final synthesized summary.
        """
        print("   🚀 OrchestratorAgent: Starting Map-Reduce workflow...")

        # Step 1: Split
        chunks = self.splitter.run(full_text)

        # Step 2: Map (sequential processing)
        print(f"   → OrchestratorAgent: Mapping {len(chunks)} chunks sequentially...")
        mapped_outputs = []
        for chunk in chunks:
            result = self.mapper.run(chunk)
            mapped_outputs.append(result)

        # Step 3: Reduce
        print("   → OrchestratorAgent: Reducing summaries to final output...")
        synthesis_document = "\n\n---\n\n".join(mapped_outputs)
        final_summary = self.reducer.run(synthesis_document)

        print("   ✓ OrchestratorAgent: Map-Reduce job complete")
        return final_summary


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


def count_tokens(text: str) -> int:
    """Estimate token count using tiktoken for GPT models (cl100k_base encoding)."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough approximation (1 token ≈ 4 characters)
        return len(text) // 4


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


def main():
    """
    Main function to process research papers.

    Usage:
        python report_to_docling.py                            # Process all PDFs
        python report_to_docling.py file1.pdf file2.pdf        # Process specific files
        python report_to_docling.py --model llama2             # Use specific model
        python report_to_docling.py --map-reduce               # Use Map-Reduce approach
        python report_to_docling.py --map-reduce --model llama2  # Combine options
    """
    # Parse command line arguments
    model = "granite4:latest"  # default model
    pdf_names = []
    use_map_reduce = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif arg == "--map-reduce":
            use_map_reduce = True
            i += 1
        elif not arg.startswith("--"):
            pdf_names.append(arg)
            i += 1
        else:
            i += 1

    # Get PDF files to process
    pdf_files = get_pdf_files(pdf_names if pdf_names else None)

    if not pdf_files:
        print("❌ No PDF files found to process.")
        return

    print("=" * 70)
    print(f"📚 Paper Summarizer with Ollama")
    print("=" * 70)
    print(f"Model: {model}")
    approach = "Map-Reduce (Agentic)" if use_map_reduce else "Traditional (Chunking)"
    print(f"Approach: {approach}")
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
        if process_paper(pdf_path, output_base_dir, model, use_map_reduce=use_map_reduce):
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
