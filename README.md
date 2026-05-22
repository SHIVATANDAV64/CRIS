# CRIS: Cross-Domain Research Intelligence System

[![BCA Academic Project](https://img.shields.io/badge/Project-BCA%20Final%20Semester-blue.svg)](#)
[![Aesthetics](https://img.shields.io/badge/Design-Premium%20Glassmorphic-purple.svg)](#)
[![LLM-Reasoning](https://img.shields.io/badge/Reasoning-AWS%20Bedrock%20%7C%20Modal-orange.svg)](#)
[![Database](https://img.shields.io/badge/Database-SQLite%20FTS5%20%2B%20Vec-green.svg)](#)

CRIS (Cross-Domain Research Intelligence System) is a state-of-the-art academic exploration, knowledge synthesis, and hypothesis generation platform. Engineered specifically for researchers, academic institutions, and cross-disciplinary scientists, CRIS bridges the boundaries between isolated fields of study. It automatically harvests literature, compiles it into an Obsidian-compatible double-linked wiki, builds interactive citation networks, and provides a reasoning-centered chat assistant capable of uncovering hidden analogies and connections across domains.

> [!IMPORTANT]
> **Developer Setup & Systems Engineering**: If you are looking for installation instructions, backend routers, database schemas, CLI execution parameters, or Modal cloud deployments, please refer to the [DEVELOPER.md](file:///c:/Users/rudra/Downloads/CRIS-Start/DEVELOPER.md) manual.

---

## 🗺️ Conceptual Architecture & Pipeline

CRIS operates as an end-to-end literature digestion and synthesis pipeline. Below is the data flow showing how a raw paper is processed, indexed, and made available for reasoning:

```
                                [ THE PIPELINE ]
                                
      1. INGEST           2. COMPILE                  3. REPRESENT
   ┌─────────────┐     ┌─────────────┐             ┌─────────────────┐
   │ arXiv (OAI) │────▶│ LLM Digest  │────────────▶│ Obsidian Wiki   │
   │ Raw Metadata│     │ (Bedrock)   │             │   sources/      │
   │  data/raw/  │     └─────────────┘             │   concepts/     │
   └─────────────┘                                 │   index.md      │
                                                   └────────┬────────┘
                                                            │
                                        ┌───────────────────┴───────────────────┐
                                        ▼ (Keyword Indexing)                    ▼ (Vector Indexing)
                               ┌─────────────────┐                     ┌─────────────────┐
                               │   SQLite FTS5   │                     │  Modal Embeds   │
                               │  Full-Text idx  │                     │  2560-dim space │
                               └────────┬────────┘                     └────────┬────────┘
                                        │                                       │
                                        └───────────────────┬───────────────────┘
                                                            ▼
                                               ┌────────────────────────┐
                                               │ Hybrid Search Engine   │
                                               │ (Precision + Semantic) │
                                               └────────────┬───────────┘
                                                            │
                                        ┌───────────────────┴───────────────────┐
                                        ▼                                       ▼
                             ┌─────────────────────┐                 ┌─────────────────────┐
                             │ Reasoning Chat      │                 │ Research Planner    │
                             │ - SSE Token Stream  │                 │ - Decomposer        │
                             │ - <think> Logs      │                 │ - Hypothesis Board  │
                             │ - Memory Extractor  │                 │ - Synthesizer       │
                             └─────────────────────┘                 └─────────────────────┘
```

---

## 🔬 Core System Concepts & Mathematical Foundations

### 1. The Vocabulary Mismatch Problem & Hybrid Search
Scientific literature is historically isolated into domain-specific silos. Researchers in machine learning might use terms like *"latent representation"* or *"sequence modeling"*, while researchers in molecular biology refer to *"folding configurations"* or *"residue sequences"*. 

CRIS solves this **Vocabulary Mismatch Problem** by combining two search paradigms:
*   **Precision Keyword Match (BM25)**: Scores papers based on exact keyword frequencies, mathematical symbols, or paper IDs.
*   **Semantic Vector Space Match (Cosine Similarity)**: Projects abstracts into a high-dimensional vector space (2560 dimensions). Similarity is computed as:
    $$\text{Similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$$
    This measures the alignment of conceptual directions, allowing the system to identify related methodology even if the vocabularies are completely different.
*   **Weighted Hybrid Search**: Using an adjustable weighting slider ($\alpha$), researchers can configure the exact balance of search retrieval:
    $$\text{Score}_{\text{hybrid}} = (1 - \alpha) \cdot \text{Score}_{\text{BM25}} + \alpha \cdot \text{Score}_{\text{semantic}}$$

### 2. Karpathy-Style Knowledge Wiki (Obsidian-Compatible)
Named after Andrej Karpathy's structural wiki pattern, CRIS builds a local, fully text-editable Markdown wiki under `data/wiki/`. The structure is designed to form a web of double-bracketed `[[wiki-links]]` that maps paper relationships.
*   **`sources/`**: Every paper gets a structured synthesis page:
    *   **Core Mechanism**: What does the paper physically do?
    *   **Key Insight**: Why does this mechanism work?
    *   **Domain-Blind Abstraction**: Restates the core mechanism without domain-specific terminology, making it readable by researchers in other fields.
*   **`concepts/`**: Aggregation pages synthesized by the LLM by analyzing all papers that reference a common theme. It highlights how the concept is used differently across domains and suggests cross-domain transfer opportunities.
*   **`entities/`**: Specific terms, datasets, and methods extracted from papers or chat sessions.
*   **`summaries/`**: Catalogs organized by date (monthly groupings) and domain folders (e.g., cs.AI, q-bio.BM) to structure the wiki.
*   **`graph.json`**: An auto-generated graph index database mapping nodes (papers, concepts, notes, entities) and their bidirectional links, visualizable in real-time.

### 3. Automatic Chat Memory Extraction
CRIS acts as an active scribe during research sessions. When you converse with the assistant, a background service (`chat_memory.py`) analyzes the exchange and automatically updates the wiki:
*   **Proper Nouns & Acronyms** are extracted and written as new files in `entities/`.
*   **Testable Claims** are logged with a "pending verification" status.
*   **Summarized Exchange Notes** are written directly to `notes/chat_<session_id>.md`, linking back to referenced papers.

### 4. Query Decomposition & Evidence Synthesis
*   **Decomposition**: High-level queries (e.g., *"How can we use neural networks to optimize protein folding?"*) are parsed by the reasoning engine into separate literature search queries, testable hypotheses, and cross-domain connection suggestions.
*   **Synthesis**: Researchers can select multiple candidate papers from the database and trigger a synthesis report. The engine aggregates findings, identifies direct contradictions between papers, and outputs a summary with inline citations.

---

## 🖥️ Web Dashboard Walkthrough (UI Features)

The frontend is a premium, glassmorphic dashboard designed for deep exploration. Below is a guide to each functional panel:

### 1. Chat Panel (The Reasoning Assistant)
*   **DeepSeek-Style Reasoning Logs**: Real-time streaming response from the inference model displays a collapsible thinking container (`<think>`). You can see the model's inner thoughts, paper query plans, and evaluations before it writes the final answer.
*   **Inline Citations & References**: All sources cited by the assistant are presented as clickable wiki-links. A sidebar shows the list of papers retrieved from the local database to generate the response.
*   **Web Search Toggle**: Allows the assistant to check the live web via SearXNG for recent news, preprints, or Wikipedia entries.

### 2. Ingestion & Build Control Panel
*   **arXiv Fetcher**:
    *   Choose relative date ranges (days back) or specify a target calendar date.
    *   Filter by domain presets (AI, Computation & Language, Machine Learning, Computer Vision, Robotics, Software Engineering, Cryptography, Databases, Information Retrieval, Neural Networks, Human-Computer Interaction, Statistics, Biomolecules, Quantitative Methods) or enter custom arXiv categories.
    *   Specify maximum papers to fetch per category.
*   **Subprocess Logs**: Displays a scrolling, color-coded terminal view of the active background tasks (Ingestion, Wiki Compilation, Search Indexing).
*   **Auto-Compile Toggle**: When enabled, the system automatically triggers LLM compilation and search indexing immediately after downloading paper metadata.

### 3. Sources Browser (Domain Explorer)
*   Browse the raw JSON repository and compiled wiki pages by domain (e.g., *Computation & Language*, *Machine Learning*).
*   Read the detailed text of compiled papers, view frontmatter tags, and trigger manual compilations.

### 4. Planner Panel (Research Board)
*   **Question Decomposer**: Type in your high-level research direction. View literature queries, hypothesis statements, and cross-domain pairs.
*   **Hypothesis Tracker**: Save candidate hypotheses to your active planner.
*   **Task Board**: Manage, assign, and track the status of literature reviews, experiments, and validation tasks.

### 5. Wiki Graph View
*   **Interactive Node-Link Map**: Color-coded nodes represent Papers (blue), Concepts (green), Notes (purple), and Entities (yellow).
*   **D3-Powered Force Simulation**: Drag, zoom, hover, and click nodes. Hovering over a node displays its title and connections; clicking it opens the compiled page details.

### 6. Settings Panel
*   Configure API targets (Amazon Bedrock region, endpoints).
*   Select default models (Darwin-36B-Opus, MiniMax M2.5).
*   Adjust search parameters (max results, hybrid alpha value).

---

## 🏃‍♀️ Researcher Playbook: Step-by-Step Scenario

### Objective: Discovering a connection between NLP Sequence Modeling and Genomic Analysis

1.  **Decompose the Problem**:
    *   Go to the **Planner** tab.
    *   Input: *"Can attention mechanisms from transformer models improve genomic sequence alignment?"*
    *   Review the output: The system will identify `cs.CL` (Language) and `q-bio.GN` (Genomics) as a key cross-domain pair, suggest search terms, and formulate hypothesis candidates.
2.  **Harvest Literature**:
    *   Navigate to the **Ingest** tab.
    *   Select presets for `Computation and Language (cs.CL)` and enter `q-bio.GN` as a custom category.
    *   Set **Days Back** to `7`, set **Max Papers** to `30`, and verify **Auto-Compile** is checked.
    *   Click **Start Ingestion** and watch the logs in the terminal viewer.
3.  **Explore Connections**:
    *   Go to the **Explorer** tab and locate a newly compiled paper on attention mechanisms.
    *   Trigger **Cross-Domain Discovery**. Select `q-bio.GN` as the target search domain.
    *   The system will use semantic embeddings to find genomics papers and explain how sequence representation methods in both fields share analogous mechanisms.
4.  **Synthesize Findings**:
    *   Add the discovered papers to the **Planner** queue.
    *   Click **Synthesize Evidence** under the Planner tab.
    *   CRIS will compile a structured paper detailing the parallels, note any contradictions in sequence alignment efficiency, and provide inline citations (`[[arxiv_id]]`) linking to your wiki.

---

## 🎓 Academic Project Context

CRIS is developed as a Bachelor of Computer Applications (BCA) Final Semester Capstone Project (2025-26). It demonstrates how combining serverless GPU execution (Modal), enterprise AI foundation models (AWS Bedrock), localized relational databases (SQLite3 FTS5), and interactive web visualizations (React + D3) can provide a production-grade research intelligence system.
