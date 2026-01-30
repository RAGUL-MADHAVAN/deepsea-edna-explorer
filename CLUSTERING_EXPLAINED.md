# How Sequences Are Clustered: Complete Explanation

This document explains **exactly** how sequences are grouped into clusters in your sample, what thresholds/parameters are used, and how the clustering algorithm works.

---

## Overview: The Clustering Pipeline

```
1. DNA Sequences → 2. DNABERT-2 Embeddings → 3. PCA Reduction → 4. HDBSCAN Clustering → 5. Cluster Labels
```

---

## Step-by-Step: How Clustering Works

### **Step 1: Sequence Embedding (DNABERT-2)**

**What happens**: Each DNA sequence is converted into a high-dimensional vector (embedding) using DNABERT-2.

**Output**: 
- Each sequence → Vector of ~768 dimensions (DNABERT-2 output size)
- Similar sequences → Similar vectors (close in high-dimensional space)

**No threshold here** - just conversion to numerical representation.

---

### **Step 2: Dimensionality Reduction (PCA)**

**What happens**: The high-dimensional embeddings (768D) are reduced to 50 dimensions using PCA.

**Code**: `src/pipeline/clustering.py:71-73`
```python
n_components = min(50, n_samples)
pca = PCA(n_components=n_components)
pca_embeddings = pca.fit_transform(embeddings)
```

**Why**: 
- HDBSCAN works better on lower-dimensional data
- Reduces noise and computational cost
- Preserves most of the variance (information)

**No threshold here** - just mathematical transformation.

---

### **Step 3: Clustering Algorithm**

**Primary Algorithm: HDBSCAN** (Hierarchical Density-Based Spatial Clustering)

**Location**: `src/pipeline/clustering.py:85-92`

#### **Key Parameters:**

##### **1. `min_cluster_size` (Dynamic Threshold)**

**Formula**: `min_cluster_size = max(2, min(5, n_samples // 2))`

**What it means**: Minimum number of sequences required to form a cluster.

**How it's calculated**:
- **Small datasets** (≤10 sequences): `min_cluster_size = 2`
- **Medium datasets** (11-20 sequences): `min_cluster_size = n_samples // 2` (e.g., 15 sequences → 7)
- **Large datasets** (>20 sequences): `min_cluster_size = 5` (capped at 5)

**Examples**:
```
n_samples = 4   → min_cluster_size = max(2, min(5, 2)) = 2
n_samples = 10  → min_cluster_size = max(2, min(5, 5)) = 5
n_samples = 50  → min_cluster_size = max(2, min(5, 25)) = 5
n_samples = 100 → min_cluster_size = max(2, min(5, 50)) = 5
```

**How it works**:
- If a group of sequences has **fewer than `min_cluster_size`** members, they are labeled as **"noise"** (cluster = -1)
- Only groups with **≥ `min_cluster_size`** sequences become actual clusters

---

##### **2. `min_samples = 1`**

**What it means**: Minimum number of neighbors required for a point to be considered a "core point".

**How it works**:
- With `min_samples=1`, HDBSCAN is more lenient
- Allows clusters to form even with sparse data
- Lower values = more clusters, higher values = fewer clusters

**Note**: This is set to `1` in the code, making clustering more sensitive to small groups.

---

##### **3. `metric = 'euclidean'`**

**What it means**: Distance metric used to measure similarity between sequences.

**How it works**:
- **Euclidean distance** in the 50-dimensional PCA space
- Formula: `distance = sqrt(sum((x_i - y_i)^2))`
- **Shorter distance** = more similar sequences
- **Longer distance** = less similar sequences

**Example**:
- Sequence A: `[0.1, 0.2, 0.3, ...]` (50 dimensions)
- Sequence B: `[0.11, 0.21, 0.31, ...]` (50 dimensions)
- Distance ≈ 0.017 (very similar → likely same cluster)
- Sequence C: `[5.0, 3.0, 1.0, ...]` (50 dimensions)
- Distance from A ≈ 5.8 (very different → different cluster)

---

### **Step 4: How HDBSCAN Groups Sequences**

**HDBSCAN is density-based**, meaning it groups sequences based on **spatial density** in the embedding space, NOT a fixed similarity percentage.

#### **The Clustering Process:**

1. **Builds a hierarchy** of clusters at different density levels
2. **Selects stable clusters** that persist across density levels
3. **Assigns cluster labels**:
   - **Positive integers** (0, 1, 2, ...) = Valid clusters
   - **-1** = Noise/outliers (sequences that don't belong to any cluster)

#### **What Determines Cluster Membership:**

**A sequence belongs to a cluster if**:
- It's within a **dense region** of other sequences
- The dense region contains **≥ `min_cluster_size`** sequences
- The cluster is **stable** across different density thresholds

**There is NO fixed "similarity percentage" threshold** (like "97% similarity"). Instead:
- Sequences are grouped based on **local density** in embedding space
- Similar sequences naturally cluster together
- The algorithm automatically finds the optimal density thresholds

---

### **Step 5: Fallback Algorithm (DBSCAN)**

**If HDBSCAN fails** (not installed or error), the pipeline falls back to **DBSCAN**.

**Location**: `src/pipeline/clustering.py:94-96`

**Parameters**:
```python
DBSCAN(eps=1.5, min_samples=2)
```

#### **`eps = 1.5`** (Distance Threshold)

**What it means**: Maximum distance between sequences to be in the same cluster.

**How it works**:
- If two sequences are within **1.5 units** (Euclidean distance in PCA space), they can be in the same cluster
- **Lower `eps`** = stricter clustering (sequences must be very close)
- **Higher `eps`** = looser clustering (sequences can be farther apart)

**Example**:
- Sequence A and B: distance = 1.2 → **Same cluster** (1.2 < 1.5)
- Sequence A and C: distance = 2.0 → **Different clusters** (2.0 > 1.5)

#### **`min_samples = 2`**

**What it means**: Minimum number of sequences in a neighborhood to form a cluster.

**How it works**:
- A sequence needs at least 2 neighbors within `eps` distance to start a cluster
- Sequences with fewer neighbors are labeled as noise (-1)

---

## Special Cases

### **Small Datasets (≤20 sequences)**

**Location**: `src/pipeline/clustering.py:53-65`

**What happens**:
- **No clustering performed** - all sequences assigned to cluster 0
- **Novelty scores set to 0** (no novelty calculation without context)
- **Reason**: Clustering algorithms need sufficient data to work meaningfully

**Code**:
```python
if n_samples <= 20:
    cluster_labels = np.zeros(n_samples, dtype=int)  # All → cluster 0
    novelty_scores = np.zeros(n_samples)  # No novelty
```

---

## Visual Example

Imagine sequences plotted in 2D space (after PCA/UMAP reduction):

```
High-Density Region (Cluster 0):
    ●
   ●●●
  ●●●●●  ← These form a cluster (dense, ≥min_cluster_size)
   ●●●
    ●

Isolated Sequence (Noise):
        ●  ← This is noise (not dense enough, cluster = -1)

Another Dense Region (Cluster 1):
                    ●
                   ●●●
                  ●●●●●  ← Another cluster
                   ●●●
                    ●
```

**HDBSCAN automatically identifies**:
- Dense regions → Clusters
- Sparse regions → Noise

---

## What You See in Your Results

### **Cluster Labels** (`clustering_results.csv`)

```csv
sequence_id,cluster,x,y,novelty_score
ASV_1,0,0.23,-0.45,0.35
ASV_2,0,0.25,-0.43,0.32
ASV_3,1,1.2,0.8,0.67
ASV_4,-1,3.5,-2.1,0.89  ← Noise/outlier
```

- **cluster = 0, 1, 2, ...**: Valid clusters
- **cluster = -1**: Noise/outliers (didn't meet `min_cluster_size`)

### **Cluster Stats** (`cluster_stats.csv`)

```csv
size,avg_novelty,classification
15,0.35,Likely Known / Variant
8,0.67,Potential Novel Species
```

- **size**: Number of sequences in cluster
- **avg_novelty**: Average novelty score for cluster
- **classification**: Based on novelty thresholds (0.4, 0.7)

---

## Summary: Clustering Thresholds

| Parameter | Value | What It Does |
|-----------|-------|--------------|
| **Algorithm** | HDBSCAN (primary) / DBSCAN (fallback) | Density-based clustering |
| **`min_cluster_size`** | `max(2, min(5, n_samples // 2))` | Minimum sequences per cluster |
| **`min_samples`** | 1 (HDBSCAN) / 2 (DBSCAN) | Minimum neighbors for core point |
| **`metric`** | 'euclidean' | Distance measure |
| **`eps`** (DBSCAN only) | 1.5 | Maximum distance for same cluster |
| **Distance Space** | 50D PCA-reduced embeddings | Where clustering happens |
| **Small Dataset** | ≤20 sequences | No clustering (all → cluster 0) |

---

## Key Points

1. **No fixed similarity percentage**: Clustering is **density-based**, not similarity-percentage-based
2. **Dynamic thresholds**: `min_cluster_size` adapts to dataset size
3. **Automatic optimization**: HDBSCAN finds optimal density levels automatically
4. **Distance-based**: Sequences close in embedding space → same cluster
5. **Noise handling**: Sequences that don't fit any cluster → labeled as noise (-1)

---

## How to Interpret Your Clusters

1. **Cluster 0, 1, 2, ...**: Groups of similar sequences (likely same or related species)
2. **Cluster -1**: Outliers/novel sequences that don't match any group
3. **Cluster size**: Larger clusters = more common sequences
4. **Novelty score**: Higher = more isolated/novel (within cluster or as noise)

---

## Adjusting Clustering Behavior

To change clustering behavior, modify `src/pipeline/clustering.py`:

### **Make clustering stricter** (fewer clusters):
```python
min_cluster_size = max(5, min(10, n_samples // 3))  # Increase minimum size
min_samples = 2  # Increase for HDBSCAN
eps = 1.0  # Decrease for DBSCAN (if used)
```

### **Make clustering looser** (more clusters):
```python
min_cluster_size = max(2, min(3, n_samples // 4))  # Decrease minimum size
min_samples = 1  # Keep at 1 (already lenient)
eps = 2.0  # Increase for DBSCAN (if used)
```

---

*This explains exactly how sequences are clustered in your pipeline. The clustering is **density-based** using **Euclidean distance** in **DNABERT-2 embedding space**, with **dynamic thresholds** that adapt to your dataset size.*
