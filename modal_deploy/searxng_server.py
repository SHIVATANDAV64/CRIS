"""
Modal.com Deployment — SearXNG Web Search Service

Installs SearXNG from source on Debian and runs it via @modal.web_server().
This avoids Docker ENTRYPOINT conflicts with Modal's runtime.

Aggregates 70+ search engines: Google, Bing, DuckDuckGo, arXiv, PubMed,
Wikipedia, Wikidata, Reddit, Hacker News, Stack Overflow, GitHub, and more.

No GPU needed — runs on CPU. Scales to zero when idle.

Deploy with:
    modal deploy modal_deploy/searxng_server.py

Test with:
    curl "https://<workspace>--cris-searxng-search.modal.run/search?q=quantum+computing&format=json"
"""
import modal

app = modal.App("cris-searxng")

# ── SearXNG Settings ─────────────────────────────────────────────────────

SEARXNG_SETTINGS = """\
use_default_settings: true

server:
  port: 8080
  bind_address: "0.0.0.0"
  limiter: false
  image_proxy: false

search:
  safe_search: 0
  autocomplete: "google"
  default_lang: "en"
  formats:
    - json
    - html

engines:
  - name: arxiv
    engine: arxiv
    categories: general
    disabled: false

  - name: pubmed
    engine: pubmed
    categories: general
    disabled: false

  - name: google
    engine: google
    disabled: false

  - name: bing
    engine: bing
    disabled: false

  - name: duckduckgo
    engine: duckduckgo
    disabled: false

  - name: wikipedia
    engine: wikipedia
    disabled: false

  - name: wikidata
    engine: wikidata
    disabled: false

  - name: reddit
    engine: reddit
    disabled: false

  - name: hacker news
    engine: hackernews
    disabled: false

  - name: stackoverflow
    engine: stackoverflow
    disabled: false

  - name: github
    engine: github
    disabled: false

  - name: google news
    engine: google_news
    disabled: false
"""


def _install_searxng():
    """Install SearXNG from source and write settings."""
    import os
    import secrets
    import subprocess

    # Install SearXNG from git
    subprocess.run(
        ["pip", "install", "git+https://github.com/searxng/searxng.git"],
        check=True,
    )

    # Write settings
    secret = secrets.token_hex(32)
    settings = SEARXNG_SETTINGS.strip() + f'\n  secret_key: "{secret}"\n'

    os.makedirs("/etc/searxng", exist_ok=True)
    with open("/etc/searxng/settings.yml", "w") as f:
        f.write(settings)

    print("SearXNG installed and configured")


# ── Image ────────────────────────────────────────────────────────────────

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "build-essential")
    .pip_install("msgspec", "PyYAML", "granian")
    .run_function(_install_searxng)
    .env({
        "SEARXNG_SETTINGS_PATH": "/etc/searxng/settings.yml",
    })
)


@app.function(
    image=image,
    cpu=1.0,
    memory=1024,
    scaledown_window=300,
    timeout=120,
    max_containers=10,
)
@modal.web_server(port=8080, startup_timeout=60)
def searxng_server():
    """
    SearXNG Web Server — runs SearXNG on port 8080.

    Modal's web_server decorator proxies traffic to port 8080.
    """
    import subprocess
    import sys
    import time
    import httpx

    # Start SearXNG via granian (what the official image uses)
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "granian",
            "--host", "0.0.0.0",
            "--port", "8080",
            "--log-level", "error",
            "searx.webapp:app",
        ],
        env={
            **__import__("os").environ,
            "SEARXNG_SETTINGS_PATH": "/etc/searxng/settings.yml",
        },
    )

    # Wait for server to be ready
    for _ in range(30):
        try:
            resp = httpx.get("http://localhost:8080/", timeout=3.0)
            if resp.status_code < 500:
                print("SearXNG is ready on port 8080")
                break
        except Exception:
            pass
        time.sleep(1)

    # Keep alive — web_server handles HTTP proxying
    import signal
    signal.pause()


@app.local_entrypoint()
def test():
    """Test the search endpoint."""
    print("Deploy first with: modal deploy modal_deploy/searxng_server.py")
    print("\nThen test with:")
    print('  curl "https://<workspace>--cris-searxng-search.modal.run/search?q=quantum+computing&format=json"')
    print('  curl "https://<workspace>--cris-searxng-search.modal.run/search?q=transformer+models&engines=arxiv,pubmed"')
