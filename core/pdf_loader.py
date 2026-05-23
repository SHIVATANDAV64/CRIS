"""
PDF Loader and Parser Utility — Downloads papers from arXiv and parses their content.
Uses opendataloader-pdf (Java-based) if available, with a robust pypdf fallback.
"""
import urllib.request
import tempfile
import sys
import os
from pathlib import Path
from typing import Optional

from config.settings import TEMP_PDF_DIR

def get_pdf_path(arxiv_id: str) -> Path:
    """Get the local target path for a downloaded PDF."""
    safe_id = arxiv_id.replace("/", "_")
    return TEMP_PDF_DIR / f"{safe_id}.pdf"

def download_pdf(arxiv_id: str, on_log: Optional[callable] = None) -> Optional[Path]:
    """
    Download a paper's PDF from arXiv if it does not already exist.
    
    Args:
        arxiv_id: arXiv paper ID (e.g., 2304.03641)
        on_log: Optional logging callback
    """
    pdf_path = get_pdf_path(arxiv_id)
    if pdf_path.exists() and pdf_path.stat().st_size > 1000:
        return pdf_path

    def log(msg: str):
        print(msg)
        if on_log:
            on_log(msg)

    # Sanitize arxiv_id for URL
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    log(f"Downloading PDF for {arxiv_id} from {url}...")
    
    try:
        # arXiv sometimes blocks basic python user agents, so set a browser header
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=30) as response, open(pdf_path, 'wb') as out_file:
            out_file.write(response.read())
            
        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
            log(f"Successfully downloaded PDF to {pdf_path} ({pdf_path.stat().st_size} bytes)")
            return pdf_path
        else:
            log(f"Downloaded file for {arxiv_id} is too small or invalid.")
            if pdf_path.exists():
                pdf_path.unlink()
            return None
    except Exception as e:
        log(f"Error downloading PDF for {arxiv_id}: {e}")
        if pdf_path.exists():
            pdf_path.unlink()
        return None

def extract_text_from_pdf(pdf_path: Path, on_log: Optional[callable] = None) -> str:
    """
    Extract text/markdown from a PDF.
    Attempts to use opendataloader-pdf first, then falls back to pypdf.
    """
    def log(msg: str):
        print(msg)
        if on_log:
            on_log(msg)

    if not pdf_path.exists():
        log(f"PDF file does not exist: {pdf_path}")
        return ""

    # 1. Attempt opendataloader-pdf
    try:
        log("Attempting PDF text extraction using opendataloader-pdf...")
        import opendataloader_pdf
        
        # opendataloader-pdf writes results to an output directory
        with tempfile.TemporaryDirectory() as temp_out_dir:
            opendataloader_pdf.convert(
                input_path=[str(pdf_path)],
                output_dir=str(temp_out_dir),
                format="markdown"
            )
            
            # The result markdown file is typically named after the PDF stem + .md
            markdown_files = list(Path(temp_out_dir).glob("*.md"))
            if markdown_files:
                parsed_text = markdown_files[0].read_text(encoding="utf-8")
                if parsed_text.strip():
                    log("Successfully parsed PDF using opendataloader-pdf!")
                    return parsed_text

    except Exception as e:
        log(f"opendataloader-pdf unavailable or failed (likely missing Java 11): {e}")

    # 2. Fallback to pypdf
    try:
        log("Falling back to pypdf for local extraction...")
        from pypdf import PdfReader
        
        reader = PdfReader(pdf_path)
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"--- Page {i+1} ---\n{page_text}")
                
        full_text = "\n\n".join(text_parts)
        if full_text.strip():
            log(f"Successfully extracted {len(full_text)} characters using pypdf fallback.")
            return full_text
            
    except Exception as e:
        log(f"pypdf extraction failed: {e}")

    log("All PDF parsing methods failed.")
    return ""
