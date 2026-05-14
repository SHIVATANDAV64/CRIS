"""
Setup Model — Download zira-researcher GGUF for local inference.

Usage:
    python scripts/setup_model.py
    python scripts/setup_model.py --quantization Q4_K_M
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from config.settings import MODELS_DIR, REASONING_MODEL_GGUF

console = Console()

# Available quantizations from mradermacher/zira-researcher-GGUF
QUANT_FILES = {
    "Q4_K_M": "zira-researcher.Q4_K_M.gguf",
    "Q5_K_M": "zira-researcher.Q5_K_M.gguf",
    "Q8_0": "zira-researcher.Q8_0.gguf",
    "IQ4_XS": "zira-researcher.IQ4_XS.gguf",
}


def main():
    parser = argparse.ArgumentParser(description="Download zira-researcher GGUF model")
    parser.add_argument(
        "--quantization",
        type=str,
        default="Q4_K_M",
        choices=list(QUANT_FILES.keys()),
        help="Quantization level (default: Q4_K_M, ~2.5GB)",
    )
    args = parser.parse_args()

    filename = QUANT_FILES[args.quantization]
    output_path = MODELS_DIR / f"zira-researcher-{args.quantization}.gguf"

    if output_path.exists():
        console.print(f"[yellow]Model already exists: {output_path}[/yellow]")
        console.print("Delete it manually to re-download.")
        return

    console.print(f"\n[bold cyan]=== CRIS Model Setup ===[/bold cyan]")
    console.print(f"Repository: {REASONING_MODEL_GGUF}")
    console.print(f"File: {filename}")
    console.print(f"Quantization: {args.quantization}")
    console.print(f"Destination: {output_path}")

    try:
        from huggingface_hub import hf_hub_download

        console.print(f"\n[cyan]Downloading... (this may take a few minutes)[/cyan]")
        downloaded_path = hf_hub_download(
            repo_id=REASONING_MODEL_GGUF,
            filename=filename,
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False,
        )

        # Rename to standardized name
        dl_path = Path(downloaded_path)
        if dl_path.exists() and dl_path != output_path:
            dl_path.rename(output_path)

        console.print(f"\n[bold green]=== Model downloaded: {output_path} ===[/bold green]")
        console.print(f"Size: {output_path.stat().st_size / (1024**3):.2f} GB")

    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        console.print("\nManual download:")
        console.print(f"  https://huggingface.co/{REASONING_MODEL_GGUF}")
        sys.exit(1)


if __name__ == "__main__":
    main()
