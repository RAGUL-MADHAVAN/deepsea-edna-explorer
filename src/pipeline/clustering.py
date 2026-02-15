
import os
import logging
import numpy as np
import pandas as pd
from pathlib import Path
import json
import pickle

from sklearn.decomposition import PCA
from sklearn.metrics import pairwise_distances

from src.pipeline.embedding import DNABertEmbedder

logger = logging.getLogger('DeepSeaEDNA.clustering')

class ClusterAnalysis:
    def __init__(self, output_dir, use_gpu=False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.embedder = DNABertEmbedder(use_gpu=use_gpu)
        self.use_gpu = use_gpu
        
    def run_clustering(self, sequences, sequence_ids):
        """
        Full clustering pipeline: Embedding -> Dim Reduction -> Clustering -> Novelty Scoring
        """
        n_samples = len(sequences)
        if n_samples == 0:
            logger.warning("No sequences to cluster.")
            return pd.DataFrame(), pd.DataFrame()

        # 1. Generate Embeddings
        logger.info("Generating DNA embeddings...")
        embeddings = self.embedder.get_embeddings(sequences)
        
        # Save embeddings
        np.save(self.output_dir / "embeddings.npy", embeddings)
        
        # 2. Build similarity index for novelty scoring
        # Prefer FAISS (fast), but fall back to sklearn if FAISS isn't available.
        index = None
        try:
            import faiss  # type: ignore
            logger.info("Building FAISS index...")
            d = embeddings.shape[1]
            index = faiss.IndexFlatL2(d)
            index.add(embeddings.astype(np.float32, copy=False))
            faiss.write_index(index, str(self.output_dir / "sequence_index.faiss"))
        except Exception as e:
            logger.warning(f"FAISS not available/failed ({e}). Falling back to sklearn NearestNeighbors for novelty scoring.")
        
        # 3. Dimensionality Reduction (PCA first, then UMAP if available)
        logger.info("Reducing dimensionality...")
        # PCA to <=50 dims for stability/speed (and to feed HDBSCAN/DBSCAN)
        n_components = min(50, n_samples, embeddings.shape[1])
        pca = PCA(n_components=n_components)
        pca_embeddings = pca.fit_transform(embeddings)
        
        # UMAP for visualization (2D) (optional)
        # IMPORTANT: For tiny datasets, UMAP import/runtime can be slow/hang on some Windows setups.
        # For n<50, we always use PCA(2D) for visualization (fast, deterministic).
        if n_samples < 2:
            umap_embeddings = np.zeros((n_samples, 2), dtype=float)
        elif n_samples < 50:
            pca_2d = PCA(n_components=2)
            umap_embeddings = pca_2d.fit_transform(embeddings)
        else:
            try:
                import umap  # type: ignore
                reducer = umap.UMAP(n_components=2, random_state=42)
                umap_embeddings = reducer.fit_transform(pca_embeddings)
            except Exception:
                logger.warning("UMAP not installed/failed. Using PCA for 2D visualization.")
                pca_2d = PCA(n_components=2)
                umap_embeddings = pca_2d.fit_transform(embeddings)

        # 4. Clustering
        # IMPORTANT: previously we forced all sequences into cluster 0 for n<=20,
        # which made (a) only one cluster id and (b) novelty_score = 0.00 always.
        # Instead, we cluster even for small n using DBSCAN with an adaptive eps.
        if n_samples == 1:
            cluster_labels = np.zeros(n_samples, dtype=int)
        else:
            logger.info("Clustering sequences...")
            # Adaptive eps based on pairwise distance distribution (works for small n)
            # eps ~ median pairwise distance * 0.6 (tighter) but never 0.
            dists = pairwise_distances(pca_embeddings, metric="euclidean")
            tri = dists[np.triu_indices_from(dists, k=1)]
            med = float(np.median(tri)) if tri.size else 0.0
            eps = max(1e-6, med * 0.6)

            # Prefer HDBSCAN if installed; else DBSCAN fallback
            try:
                import hdbscan  # type: ignore
                min_cluster_size = max(2, min(5, n_samples // 2))
                clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=1, metric='euclidean')
                cluster_labels = clusterer.fit_predict(pca_embeddings)
            except Exception as e:
                logger.warning(f"HDBSCAN not available/failed ({e}). Falling back to DBSCAN (eps={eps:.4f}).")
                from sklearn.cluster import DBSCAN
                cluster_labels = DBSCAN(eps=eps, min_samples=1).fit_predict(pca_embeddings)

        # If everything became "noise" (-1) in a tiny run, treat each point as its own cluster
        # so the UI/users can see distinct cluster IDs for distinct sequences.
        if n_samples > 1 and np.all(cluster_labels == -1) and n_samples <= 20:
            logger.info("All points labeled as noise on a tiny dataset; assigning unique clusters per sequence.")
            cluster_labels = np.arange(n_samples, dtype=int)

        # 5. Novelty Scoring (now computed even for small n)
        logger.info("Calculating novelty scores...")
        novelty_scores = self._calculate_novelty(embeddings, cluster_labels, index)
        
        # 6. Prepare Results
        results_df = pd.DataFrame({
            'sequence_id': sequence_ids,
            'cluster': cluster_labels,
            'x': umap_embeddings[:, 0],
            'y': umap_embeddings[:, 1],
            'novelty_score': novelty_scores
        })
        
        # Interpret clusters
        cluster_stats = self._interpret_clusters(results_df)
        
        # Save results
        results_df.to_csv(self.output_dir / "clustering_results.csv", index=False)
        cluster_stats.to_csv(self.output_dir / "cluster_stats.csv", index=False)
        
        return results_df, cluster_stats
        
    def _calculate_novelty(self, embeddings, labels, index):
        """
        Calculate a novelty score based on isolation.
        In a real scenario with known species, we would measure distance to known embeddings.
        Here we measure distance to nearest neighbors and cluster density.
        """
        # Distance to 5th nearest neighbor as a proxy for isolation
        if embeddings.shape[0] == 1:
            mean_dist = np.ones((1,), dtype=float)
        elif index is not None:
            D, _ = index.search(embeddings.astype(np.float32, copy=False), k=6)
            mean_dist = np.mean(D[:, 1:], axis=1)
        else:
            from sklearn.neighbors import NearestNeighbors
            nn = NearestNeighbors(n_neighbors=min(6, embeddings.shape[0]), metric="euclidean")
            nn.fit(embeddings)
            D, _ = nn.kneighbors(embeddings)
            if D.shape[1] <= 1:
                mean_dist = np.ones((embeddings.shape[0],), dtype=float)
            else:
                mean_dist = np.mean(D[:, 1:], axis=1)
        
        # Normalize distances to 0-1 using dataset min-max to avoid saturation
        md = mean_dist.astype(float)
        md_min = float(np.min(md))
        md_max = float(np.max(md))
        if md_max <= md_min + 1e-12:
            scaled = np.zeros_like(md)
        else:
            scaled = (md - md_min) / (md_max - md_min)
        score = np.sqrt(np.clip(scaled, 0.0, 1.0)) * 0.98
        if score.shape[0] > 1:
            noise = np.linspace(0.0, 0.02, score.shape[0])
            score = np.clip(score + noise, 0.0, 0.98)
        
        return score

    def _interpret_clusters(self, df):
        """
        Summarize cluster statistics.
        """
        stats = df.groupby('cluster').agg({
            'sequence_id': 'count',
            'novelty_score': 'mean'
        }).rename(columns={'sequence_id': 'size', 'novelty_score': 'avg_novelty'})
        
        # Label clusters
        def label_cluster(row):
            if row.name == -1:
                return "Noise / Unclassified"
            if row['avg_novelty'] > 0.7:
                return "High-Novelty Candidate"
            elif row['avg_novelty'] > 0.4:
                return "Potential Novel Species"
            else:
                return "Likely Known / Variant"
                
        stats['classification'] = stats.apply(label_cluster, axis=1)
        return stats
