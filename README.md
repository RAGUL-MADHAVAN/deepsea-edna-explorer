# DeepSea eDNA Explorer (Hackathon Demo)

DeepSea eDNA Explorer is a **Smart India Hackathon demo** that delivers an end-to-end, explainable pipeline for **deep‑sea environmental DNA (eDNA)** analysis. The focus is a working, **complete demo** rather than production-grade bioinformatics accuracy.

## Problem Statement (SIH)

Extract taxonomy and biodiversity insights from deep‑sea eDNA reads using a pipeline that can detect **known and unknown taxa**. The core innovation is **AI-based DNA embeddings + clustering** to surface novel species groups, with classical bioinformatics steps represented conceptually.

## What This Demo Delivers

- **End-to-end pipeline** from raw reads → clusters → annotations → abundance → report.
- **Explainable workflow** with clear stage logs.
- **Web interface** to upload samples, run analysis, and view outputs.
- **Simulated HMM & BLAST stages** (documented as demo abstractions).

## Key Idea: Hybrid AI + Bioinformatics

We keep the **logical stages** used in real pipelines:

1. **QC / preprocessing** (simulated quality filtering)
2. **HMM marker / eukaryote detection** (simulated)
3. **BLAST similarity search** (simulated)
4. **AI embedding + clustering** (PyTorch + HDBSCAN)
5. **Taxonomic annotation** (hybrid, with simulated references)
6. **Abundance + diversity**
7. **Visualization + report**

> **Important:** HMM and BLAST are **conceptual stages** for this demo. We do **not** re-implement HMMER or BLAST. The pipeline uses lightweight heuristics/mock outputs with clear logging so the flow is visible and explainable.

## Pipeline Stages (CLI)

The CLI pipeline runs the following steps in `src/pipeline.py`:

1. **QC / Preprocessing**
   - Simulated quality filtering (keeps ~90% reads) for demo.
2. **HMM Marker Detection (Simulated)**
   - Mock HMM-based marker and eukaryote detection.
3. **BLAST Similarity Search (Simulated)**
   - Mock top-hit similarity labeling.
4. **Embedding + Clustering (AI Core)**
   - One-hot encoding → PyTorch embedder → HDBSCAN clustering.
5. **Taxonomic Annotation (Hybrid)**
   - Simulated taxonomy labels (reference-based + reference-free).
6. **Abundance & Diversity**
   - Relative abundance + Shannon/Simpson metrics.
7. **Report**
   - Generates `report.html` + cluster plot.

### Required outputs (always generated)

- `classified/classification_results.pkl`
- `annotated/annotation_results.pkl`
- `abundance/abundance_results.pkl`
- `results/visualizations/sequence_clusters.png`
- `results/report.html`

## Web App (Flask)

The web app (`web/app.py`) provides:

- User login and project management
- Sample upload (FASTA/FASTQ)
- **Run Analysis** button → triggers the pipeline via subprocess
- Analysis status updates (Pending → Processing → Completed/Failed)
- Links to pipeline outputs (report, cluster plot, CSVs)

## What’s Real vs Simulated

**Real / Implemented:**

- Pipeline orchestration and logging
- AI embedding + clustering (PyTorch + HDBSCAN)
- Abundance + diversity calculation
- Flask web interface + pipeline integration

**Simulated / Mocked for Demo:**

- HMM marker detection
- BLAST similarity search
- Quality filtering (random keep %)
- Reference database labels

## How to Run (Web Demo)

**Recommended Python:** 3.10 or 3.11

```bash
git clone https://github.com/RAGUL-MADHAVAN/deepsea-edna-explorer.git
cd deepsea-edna-explorer
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows

pip install -r requirements-web.txt
python web\app.py
```

Open: http://127.0.0.1:5000

## How to Run (CLI Pipeline)

```bash
pip install -r requirements.txt
python src/pipeline.py --input data\raw\sample1.fastq --output results\demo_run
```

## Notes & Constraints (Hackathon)

- This is a **demo-first** build.
- HMM/BLAST are **conceptual stages only**.
- Focus is on explainability and end-to-end flow.
- No heavy external tools (BLAST/HMMER/fastp/Prokka) are installed.

## Credits

Smart India Hackathon team project: **DeepSea eDNA Explorer**
