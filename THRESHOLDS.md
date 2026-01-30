# Threshold Values and How They Work

This document explains all threshold values used in the DeepSea eDNA Explorer pipeline and how they control the analysis workflow.

---

## 1. **Quality Control Thresholds**

### `min_length` (Default: 100 bp)
**Location**: `src/pipeline/qc.py:45`, `src/utils/preprocessing.py:19`

**What it does**: Filters out sequences shorter than this length.

**How it works**:
- Sequences with length < `min_length` are discarded
- Used in `filter_length()` method
- Prevents analysis of fragments too short to be informative

**Example**: If `min_length=100`, a sequence of 85 bp is discarded, but a 120 bp sequence passes.

---

### `min_quality` (Default: 40 / Q30)
**Location**: `src/utils/preprocessing.py:19`, Web UI forms

**What it does**: Minimum Phred quality score for sequence filtering.

**How it works**:
- Q30 = 99.9% base call accuracy
- Q40 = 99.99% base call accuracy
- Used by `fastp` tool (if available) or simulated in Python fallback
- Lower quality sequences are trimmed or discarded

**Typical values**:
- Q30: Standard for most analyses
- Q40: High-quality requirement

---

## 2. **Denoising Thresholds**

### `min_abundance` (Default: 2)
**Location**: `src/pipeline/denoising.py:60`

**What it does**: Minimum number of occurrences required for a sequence to be considered a valid ASV (Amplicon Sequence Variant).

**How it works**:
- Sequences appearing only once (singletons) are filtered out as likely sequencing errors
- **Adaptive behavior**: For datasets with ≤10 sequences, automatically set to `1` to avoid filtering everything
- **Safety fallback**: If no ASVs are produced with `min_abundance=2`, automatically reruns with `min_abundance=1`

**Example**:
- Sequence appears 3 times → **Kept** (≥ 2)
- Sequence appears 1 time → **Filtered** (unless dataset is small)

**Code logic**:
```python
if len(seqs) <= 10:
    min_abundance = 1  # Don't filter small datasets
if count >= min_abundance:
    # Keep sequence
```

---

### `max_seqs` for Remote BLAST (Default: 25)
**Location**: `src/pipeline/taxonomy.py:34`

**What it does**: Maximum number of representative sequences to send to remote NCBI BLAST.

**How it works**:
- Remote BLAST is slow and rate-limited
- If more than `max_seqs` sequences need BLAST, only the first `max_seqs` are processed
- Prevents timeouts and API rate limiting

**Example**: If you have 100 representative sequences, only the first 25 are sent to remote BLAST.

---

## 3. **Clustering Thresholds**

### `min_cluster_size` (Dynamic: 2-5)
**Location**: `src/pipeline/clustering.py:88`

**What it does**: Minimum number of sequences required to form a cluster in HDBSCAN.

**How it works**:
- **Dynamic calculation**: `min_cluster_size = max(2, min(5, n_samples // 2))`
- For small datasets: minimum of 2 sequences per cluster
- For large datasets: up to 5 sequences per cluster, or half the dataset size (whichever is smaller)
- Sequences not meeting this threshold are labeled as "noise" (cluster = -1)

**Example**:
- 10 sequences → `min_cluster_size = max(2, min(5, 5)) = 5`
- 100 sequences → `min_cluster_size = max(2, min(5, 50)) = 5`
- 4 sequences → `min_cluster_size = max(2, min(5, 2)) = 2`

---

### `eps` for DBSCAN Fallback (Default: 1.5)
**Location**: `src/pipeline/clustering.py:96`

**What it does**: Maximum distance between sequences to be in the same cluster (when HDBSCAN is unavailable).

**How it works**:
- Used only if HDBSCAN fails
- Sequences within `eps` distance are grouped together
- Lower values = stricter clustering (fewer clusters)
- Higher values = looser clustering (more sequences per cluster)

---

### `min_samples` for DBSCAN (Default: 2)
**Location**: `src/pipeline/clustering.py:96`

**What it does**: Minimum number of sequences in a neighborhood to form a cluster.

**How it works**:
- A sequence needs at least `min_samples` neighbors within `eps` distance to start a cluster
- Used only in DBSCAN fallback mode

---

## 4. **Novelty Score Thresholds**

### Novelty Score Calculation
**Location**: `src/pipeline/clustering.py:120-143`

**How it works**:
- Measures distance to 5th nearest neighbor in embedding space
- Formula: `score = 1 - exp(-mean_distance)`
- Range: 0.0 (very similar to known sequences) to ~1.0 (highly novel/isolated)

---

### Novelty Classification Thresholds

#### **0.7** - High Novelty Threshold
**Location**: `src/pipeline/clustering.py:158`, `src/pipeline/manager.py:179`

**What it does**: Clusters with average novelty > 0.7 are labeled "High-Novelty Candidate"

**How it works**:
```python
if avg_novelty > 0.7:
    return "High-Novelty Candidate"
```

---

#### **0.5** - Potential Novel Species Threshold
**Location**: `src/pipeline/clustering.py:160`, `src/pipeline/manager.py:180`

**What it does**: Clusters with average novelty > 0.5 are labeled "Potential Novel Species"

**How it works**:
```python
elif avg_novelty > 0.5:
    return "Potential Novel Species"
```

---

#### **0.4** - Moderate Novelty Threshold
**Location**: `src/pipeline/clustering.py:160`

**What it does**: Clusters with average novelty > 0.4 are labeled "Potential Novel Species" (lower threshold in cluster interpretation)

**How it works**:
- Used in cluster-level classification
- Lower than sequence-level threshold (0.5) to catch more candidates

---

#### **0.8** - Very High Novelty (Unclassified)
**Location**: `src/pipeline/manager.py:179`

**What it does**: Unclassified sequences with novelty > 0.8 are labeled "High-Novelty Candidate"

**How it works**:
```python
if row['scientific_name'] == 'Unclassified':
    if row['novelty_score'] > 0.8:
        return "High-Novelty Candidate"
```

---

## 5. **Taxonomy Classification Thresholds**

### `identity_percent` (BLAST Identity)
**Location**: `src/pipeline/taxonomy.py:80, 144`

**What it does**: Percentage of identical bases between query and BLAST hit.

**How it works**:
- Calculated as: `(hsp.identities / hsp.align_length) * 100`
- Range: 0% (no match) to 100% (perfect match)
- Higher values indicate better taxonomic assignment confidence

**Typical interpretation**:
- **≥ 97%**: Species-level match
- **≥ 95%**: Genus-level match
- **< 90%**: Unreliable or variant/strain

---

### `e_value` (BLAST E-value)
**Location**: `src/pipeline/taxonomy.py:86, 150`

**What it does**: Expected number of random matches with the same score.

**How it works**:
- Lower e-value = more significant match
- **< 1e-5**: Significant match
- **< 1e-10**: Highly significant match
- Used to filter out spurious alignments

**Note**: Currently, the pipeline accepts any e-value from BLAST (no filtering threshold applied). The e-value is recorded but not used to reject matches.

---

### `confidence` Threshold (Default: 90%)
**Location**: `src/pipeline/manager.py:183`

**What it does**: Minimum identity_percent to classify as "Known Species" vs "Variant/Strain"

**How it works**:
```python
if row['confidence'] < 90:
    return "Variant / Strain"
else:
    return "Known Species"
```

**Example**:
- Identity = 95% → "Known Species"
- Identity = 85% → "Variant / Strain"

---

## 6. **Status Determination Logic**

**Location**: `src/pipeline/manager.py:177-184`

The final status combines taxonomy and novelty:

```python
def determine_status(row):
    if row['scientific_name'] == 'Unclassified':
        if row['novelty_score'] > 0.8: return "High-Novelty Candidate"
        if row['novelty_score'] > 0.5: return "Potential Novel Species"
        return "Unknown"
    else:
        if row['confidence'] < 90: return "Variant / Strain"
        return "Known Species"
```

**Decision Tree**:
1. **Unclassified + Novelty > 0.8** → "High-Novelty Candidate"
2. **Unclassified + Novelty > 0.5** → "Potential Novel Species"
3. **Unclassified + Novelty ≤ 0.5** → "Unknown"
4. **Classified + Identity < 90%** → "Variant / Strain"
5. **Classified + Identity ≥ 90%** → "Known Species"

---

## 7. **Abundance Thresholds**

### No Explicit Filtering Threshold
**Location**: `src/pipeline/abundance.py`

**What it does**: All sequences with counts > 0 are included in abundance tables.

**Note**: The web UI (`visualizations.html`) has a slider for filtering by minimum abundance percentage (default: 0.5%), but this is only for visualization, not for actual abundance calculation.

---

## 8. **Small Dataset Handling**

### `n_samples <= 20` - Small Dataset Threshold
**Location**: `src/pipeline/clustering.py:53`

**What it does**: For datasets with ≤20 sequences, uses simplified clustering.

**How it works**:
- All sequences assigned to cluster 0 (no clustering)
- Novelty scores set to 0 (no novelty calculation without context)
- Uses PCA for 2D visualization instead of UMAP

**Rationale**: Clustering algorithms need sufficient data to work meaningfully. Small datasets are treated as single groups.

---

## 9. **Embedding Thresholds**

### `max_length` (Default: 512)
**Location**: `src/pipeline/embedding.py:84`

**What it does**: Maximum sequence length for DNABERT-2 embedding.

**How it works**:
- Sequences longer than 512 bp are truncated
- Sequences shorter than 512 bp are padded
- DNABERT-2 model has a maximum position embedding of 512

---

### `batch_size` (Default: 32)
**Location**: `src/pipeline/embedding.py:84`

**What it does**: Number of sequences processed in parallel during embedding generation.

**How it works**:
- Larger batch = faster processing but more memory
- Smaller batch = slower but less memory usage

---

## Summary Table

| Threshold | Default Value | Purpose | Location |
|-----------|--------------|---------|----------|
| `min_length` | 100 bp | Filter short sequences | `qc.py`, `preprocessing.py` |
| `min_quality` | 40 (Q40) | Filter low-quality bases | `preprocessing.py` |
| `min_abundance` | 2 | Filter sequencing errors | `denoising.py` |
| `max_seqs` (BLAST) | 25 | Limit remote BLAST queries | `taxonomy.py` |
| `min_cluster_size` | 2-5 (dynamic) | Minimum cluster size | `clustering.py` |
| `novelty > 0.7` | 0.7 | High novelty classification | `clustering.py`, `manager.py` |
| `novelty > 0.5` | 0.5 | Potential novel species | `clustering.py`, `manager.py` |
| `novelty > 0.8` | 0.8 | Very high novelty (unclassified) | `manager.py` |
| `identity_percent` | 90% | Known vs Variant threshold | `manager.py` |
| `max_length` (embedding) | 512 bp | DNABERT-2 input limit | `embedding.py` |
| `n_samples <= 20` | 20 | Small dataset threshold | `clustering.py` |

---

## How to Adjust Thresholds

### Via Command Line (Pipeline)
Currently, thresholds are hardcoded in the modules. To adjust:

1. **Quality thresholds**: Modify `src/pipeline/qc.py` or `src/utils/preprocessing.py`
2. **Denoising**: Modify `min_abundance` in `src/pipeline/denoising.py:60`
3. **Clustering**: Modify thresholds in `src/pipeline/clustering.py`
4. **Taxonomy**: Modify `confidence` threshold in `src/pipeline/manager.py:183`

### Via Web UI
- **Confidence threshold**: Available in upload/analysis forms (default: 60-80%)
- **Quality threshold**: Available in run analysis form (default: Q30)
- **Abundance filter**: Available in visualizations page (default: 0.5%, visualization only)

---

## Recommendations

1. **For Deep-Sea Novel Discovery**: Lower `min_abundance` to 1, increase novelty thresholds to 0.6-0.8
2. **For High-Quality Analysis**: Use `min_quality=40` (Q40), `min_length=150`
3. **For Large Datasets**: Increase `max_seqs` for remote BLAST if you have many representative sequences
4. **For Small Datasets**: The pipeline automatically adjusts thresholds (e.g., `min_abundance=1` for ≤10 sequences)

---

*Last updated: Based on current codebase analysis*
