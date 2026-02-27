# DeepSea eDNA Explorer

Modern, end‑to‑end platform for deep‑sea environmental DNA (eDNA) analysis. It includes:
- A web app for uploading samples, running analyses, visualizing results, generating reports, and chatting with an AI assistant.
- A modular pipeline (Python) for QC, embedding, clustering, taxonomy, abundance and reporting.

This README explains the flow from install → run → analyze → report → AI assistant, and where each piece lives in the repo.

---

## Quick Start (TL;DR)

```bash
# 1) Create virtual env and install deps
python -m venv venv
.\venv\Scripts\activate      # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 2) Set AI assistant key (optional but recommended)
# Windows PowerShell (current session):
$env:OPENAI_API_KEY = "sk-...your-key..."
# macOS/Linux (bash/zsh):
export OPENAI_API_KEY="sk-...your-key..."

# 3) Start the web app
cd web
python app.py

# Open http://localhost:5000
```

---

## Repository Structure

- web/
  - app.py               – Flask app entrypoint and configuration
  - routes.py            – All web routes (dashboard, projects, samples, AI API)
  - models.py            – SQLAlchemy models (User, Project, Sample, Analysis)
  - templates/           – Jinja2 templates for pages
  - static/              – CSS, JS, images
- src/
  - pipeline/            – Modular pipeline (QC, denoising, clustering, taxonomy, etc.)
  - utils/               – Shared utilities (I/O, visualization, external tools)
- tests/
  - test_pipeline.py     – Example tests for pipeline components

---

## End‑to‑End Flow

1) Upload Data
- In the web UI, create a Project and add Samples (FASTA/FASTQ/CSV/XLSX).
- The server will convert CSV/XLSX/FASTQ into FASTA when needed for downstream steps.

2) Run Analysis
- From a Sample page, start an Analysis. The pipeline runs in the background:
  - Preprocessing/QC (optional)
  - Denoising/ASV generation (VSEARCH if available; Python fallback otherwise)
  - Embedding (DNABERT‑2 if available; k‑mer fallback otherwise)
  - Clustering (HDBSCAN) and novelty scoring
  - Taxonomy (BLAST/reference matching when available)
  - Abundance estimation and basic biodiversity metrics
  - Visualization assets and report data generation
- Results are stored under a run‑specific output directory.

3) Visualize
- Dashboard, Project, Sample pages summarize status and results.
- Report pages show charts (pie, bar, novelty plots), clustering tiles, and summary metrics.
- Values are formatted for readability; charts use a scientific color palette for clarity.

4) Report & Print/PDF
- Use the report page’s print/download to produce a clean PDF:
  - Non‑essential UI is hidden in print view.
  - Cards are arranged for paper with consistent spacing and titles.

5) AI Assistant (Optional but powerful)
- Ask questions about your data or methods in the AI Assistant page.
- The assistant sends your prompt (and optional project/sample context) to an OpenAI‑compatible endpoint.
- Responses appear in the chat with basic formatting and linkification.

---

## Web App: Configuration

Environment variables (read by the backend). You can set them per‑session in your shell or persist in your OS environment.

- OPENAI_API_KEY – required to enable the AI assistant.
- OPENAI_BASE_URL – optional; defaults to `https://api.openai.com/v1` (use this if pointing to an OpenAI‑compatible provider).
- OPENAI_MODEL – optional; defaults to `gpt-4o-mini` (e.g., `gpt-4o`).
- MONGO_URI – optional; defaults to `mongodb://localhost:27017/deepsea_edna`.

Windows PowerShell (current session):
```powershell
$env:OPENAI_API_KEY = "sk-...your-key..."
```

macOS/Linux:
```bash
export OPENAI_API_KEY="sk-...your-key..."
```

Instance configuration file (optional):
- The app will also load `web/instance/config.py` if present (ignored by Git).
- Example contents:
```python
OPENAI_API_KEY = "sk-...your-key..."
OPENAI_MODEL = "gpt-4o-mini"
# OPENAI_BASE_URL = "https://api.openai.com/v1"
```

Start the web app:
```bash
cd web
python app.py
# Browse http://localhost:5000
```

---

## Pipeline: Command‑Line Usage

Run the full pipeline on a FASTQ/FASTA file:
```bash
python src/pipeline.py --input data/raw/sample1.fastq --output data/processed/results/
```

Key modules (also invokable independently where applicable):
- Embedding & Clustering: `src/pipeline/embedding.py`, `src/pipeline/clustering.py`
- Taxonomy: `src/pipeline/taxonomy.py` (uses BLAST when available)
- Abundance: `src/pipeline/abundance.py` and `src/abundance/estimate.py`
- Visualization: `src/utils/visualization.py`

Optional external tools (improve results if installed):
- VSEARCH (denoising), Bowtie2 (mapping), MEGAHIT/metaSPAdes (assembly), MAFFT/EPA‑ng/GAPPA (phylogeny)
- The code auto‑detects tools and falls back to Python implementations when absent.

Input formats:
- FASTQ/FASTA directly supported; CSV/XLSX with sequence columns are converted internally.

Outputs:
- Cluster assignments, taxonomy tables (where matched), abundance summaries, novelty scores, figures.

---

## Development

Run tests (if `pytest` is installed):
```bash
pytest -q
```

Code style:
- Python modules follow a modular structure. Avoid committing secrets.
- Web templates are Jinja2; static assets live under `web/static/`.

---

## Troubleshooting

- “AI not configured: set OPENAI_API_KEY…” in chat
  - Set `OPENAI_API_KEY` in your environment or `web/instance/config.py`, then restart the server.

- 400 “CSRF token missing” on API calls from the browser
  - Make sure the page includes the CSRF meta tag (from base template). The bundled JS automatically attaches the `X‑CSRFToken` header.

- External tools not found
  - The pipeline will fall back to pure‑Python modes. Install tools (e.g., VSEARCH, Bowtie2) and ensure they’re in `PATH` for full functionality.
---

## Credits & License
- Built for deep‑sea biodiversity research with a focus on high‑clarity scientific reporting and modern UX.
- License: MIT (see LICENSE).

If you use DeepSea eDNA Explorer in your research, please cite the project (citation details forthcoming).
