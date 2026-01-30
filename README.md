# DeepSeaEDNA: AI-Driven Pipeline for Deep-Sea Environmental DNA Analysis
## Overview

DeepSeaEDNA is a discovery & analysis tool designed specifically for analyzing environmental DNA (eDNA) from deep-sea ecosystems. This system uses fixed DNA embeddings and unsupervised clustering to discover biodiversity patterns without any supervised or unsupervised model training.

### Key Features
- **Database-Independent Analysis**: Minimizes reliance on incomplete reference databases for deep-sea organisms
- **Fixed Embedding Classification**: Uses deterministic projections to identify patterns in sequence data
- **Taxonomic Annotation**: Assigns taxonomic classifications using reference-matching and novelty discovery
- **Abundance Estimation**: Provides quantitative measures of species abundance in samples
- **Novel Taxa Discovery**: Enables identification of previously unknown deep-sea organisms
- **Unsupervised Clustering**: Groups sequences based on inherent similarity using HDBSCAN

## Background

The deep ocean harbors a significant portion of global biodiversity, much of which remains undiscovered due to its inaccessibility. Environmental DNA (eDNA) has emerged as a powerful, non-invasive tool for studying these ecosystems by capturing genetic traces of organisms from environmental samples.

However, traditional bioinformatic pipelines for eDNA analysis rely heavily on reference databases like SILVA, PR2, or NCBI, which lack comprehensive sequences for deep-sea eukaryotes. This leads to misclassifications, unassigned reads, or underestimation of biodiversity.

## Installation

### Prerequisites

- Python 3.8+
- 16GB+ RAM

### Setup

```bash
# Clone the repository
git clone https://github.com/your-organization/DeepSeaEDNA.git
cd DeepSeaEDNA

# Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Workflow

```bash
# Run the complete pipeline on a sample
python src/pipeline.py --input data/raw/sample1.fastq --output data/processed/results/
```

### Pipeline Components

The pipeline consists of several modules that can be run independently:

1. **Sequence Classification**
   ```bash
   python src/classification/classify.py --input data/raw/sample1.fastq --output data/processed/classified/
   ```

2. **Taxonomic Annotation**
   ```bash
   python src/annotation/annotate.py --input data/processed/classified/ --output data/processed/annotated/
   ```

3. **Abundance Estimation**
   ```bash
   python src/abundance/estimate.py --input data/processed/annotated/ --output data/processed/abundance/
   ```

## Data Requirements

- Raw eDNA sequencing data (FASTQ format)
- Optional: Reference sequences for hybrid classification approach

## Output

The pipeline generates several outputs:

- Classified sequence clusters
- Taxonomic assignments (Reference-matched or Potential Novel)
- Abundance estimates for identified taxa
- Biodiversity metrics and visualizations

## Contributing

Contributions to improve DeepSeaEDNA are welcome. Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Citation

If you use DeepSeaEDNA in your research, please cite our paper:

```
[Citation information will be added upon publication]
```

## Acknowledgments

- Centre for Marine Living Resources and Ecology (CMLRE)
- [Other collaborators and funding sources]