"""
Modal Serverless Wiki Compiler — Dedicated service for downloading PDFs, 
extracting text using opendataloader-pdf (with Java 11 JRE), and compiling 
papers using the MiniMax model.

Run:
    modal deploy modal_deploy/serve_app.py
"""
import modal
import os
import urllib.request
import tempfile
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Setup Modal App
app = modal.App("cris-wiki-compiler")

# PROJECT_ROOT path resolver
PROJECT_ROOT = Path(__file__).parent.parent

# Build image with Python 3.11, Java 11 (JRE) for opendataloader-pdf, and all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("default-jre")  # Java runtime for opendataloader-pdf
    .pip_install(
        "openai>=1.30.0",
        "fastapi[standard]",
        "python-dotenv>=1.0.0",
        "pypdf>=4.0.0",
        "opendataloader-pdf>=0.1.0",
    )
    # Map the config directory into the container for accessing templates & prompts
    .add_local_dir(PROJECT_ROOT / "config", remote_path="/app/config")
)

# Read local .env configurations for Bedrock APIs, etc.
env_path = PROJECT_ROOT / ".env"
env_dict = {}
if env_path.exists():
    from dotenv import dotenv_values
    env_dict = {k: v for k, v in dotenv_values(env_path).items() if v}

# Create compiler secret unconditionally so local and remote signatures match
compiler_secret = modal.Secret.from_dict(env_dict if env_dict else {"CRIS_MODAL_COMPILER_ENV": "active"})

class PaperInput(BaseModel):
    arxiv_id: str
    title: str
    authors: List[str]
    categories: str
    created: str
    abstract: str

@app.function(
    image=image,
    secrets=[compiler_secret],
    timeout=600,
)
@modal.asgi_app()
def serve():
    api = FastAPI(title="CRIS Serverless Compiler Service")

    @api.post("/compile")
    async def compile_paper(paper: PaperInput):
        """
        Serverless flow to download, extract, and compile a paper.
        """
        arxiv_id = paper.arxiv_id
        
        # 1. Download PDF to temp file
        pdf_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        pdf_path = Path(pdf_file.name)
        pdf_file.close()
        
        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=30) as response, open(pdf_path, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            # Fall back to using the abstract if the PDF download fails
            print(f"Failed to download PDF for {arxiv_id}: {e}")
            pdf_path = None
            
        # 2. Extract PDF text
        full_text = ""
        if pdf_path and pdf_path.exists() and pdf_path.stat().st_size > 1000:
            # First attempt opendataloader-pdf
            try:
                import opendataloader_pdf
                with tempfile.TemporaryDirectory() as temp_out_dir:
                    opendataloader_pdf.convert(
                        input_path=[str(pdf_path)],
                        output_dir=str(temp_out_dir),
                        format="markdown"
                    )
                    markdown_files = list(Path(temp_out_dir).glob("*.md"))
                    if markdown_files:
                        full_text = markdown_files[0].read_text(encoding="utf-8")
            except Exception as e:
                print(f"opendataloader-pdf failed (likely missing Java 11 JRE inside container?): {e}")
                
            # Fallback to pypdf
            if not full_text.strip():
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(pdf_path)
                    text_parts = []
                    for i, page in enumerate(reader.pages):
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"--- Page {i+1} ---\n{page_text}")
                    full_text = "\n\n".join(text_parts)
                except Exception as e:
                    print(f"pypdf fallback failed: {e}")
                    
        # Cleanup temp PDF file
        if pdf_path and pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass
                
        # 3. Setup client and messages
        from openai import OpenAI
        
        api_key = os.getenv("BEDROCK_API_KEY")
        base_url = os.getenv("BEDROCK_BASE_URL", "https://bedrock-mantle.us-east-1.api.aws/v1")
        model_name = os.getenv("BEDROCK_MODEL", "minimax.minimax-m2.5")
        
        if not api_key:
            raise HTTPException(status_code=500, detail="BEDROCK_API_KEY environment variable not set on Modal.")
            
        client = OpenAI(base_url=base_url, api_key=api_key)
        
        # Load system prompts dynamically
        import sys
        sys.path.append("/app")
        from config.prompts import WIKI_COMPILER_SYSTEM, WIKI_COMPILER_USER
        
        authors_list = [a for a in paper.authors if a]
        authors_str = ", ".join(authors_list[:5])
        if len(authors_list) > 5:
            authors_str += f" et al. ({len(paper.authors)} total)"
            
        if full_text.strip():
            user_message = f"""Compile this paper into a wiki entry. You are provided with the full text of the paper. Use it to construct a highly detailed, accurate, and deep research wiki entry.

**arXiv ID**: {arxiv_id}
**Title**: {paper.title}
**Authors**: {authors_str}
**Categories**: {paper.categories}
**Published**: {paper.created}

**Full Paper Content**:
{full_text[:60000]}"""
        else:
            user_message = WIKI_COMPILER_USER.format(
                arxiv_id=arxiv_id,
                title=paper.title,
                authors=authors_str,
                categories=paper.categories,
                published=paper.created,
                abstract=paper.abstract,
            )
            
        # 4. Call Model
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": WIKI_COMPILER_SYSTEM},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=8192,
            )
            return {"arxiv_id": arxiv_id, "wiki_content": response.choices[0].message.content}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Model invocation failed: {str(e)}")

    return api
