#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Visualization Utilities

This module provides functions for generating visualizations and reports in the eDNA pipeline.
"""

import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from src.utils.io import load_results

# Set up logger
logger = logging.getLogger('DeepSeaEDNA.utils.visualization')


def plot_sequence_clusters(visualization_data, output_dir):
    """
Generate visualization of sequence clusters.
    
Args:
    visualization_data: Dictionary containing 2D embeddings and cluster labels
    output_dir: Directory to save visualization
    """
    logger.info("Generating sequence cluster visualization")
    
    # Create visualizations directory if it doesn't exist
    vis_dir = output_dir / 'visualizations'
    vis_dir.mkdir(exist_ok=True)
    
    # Extract data
    embeddings_2d = visualization_data['embeddings_2d']
    cluster_labels = visualization_data['cluster_labels']
    
    # Create figure
    plt.figure(figsize=(10, 8))
    
    # Create a colormap that handles noise points (-1) differently
    unique_labels = set(cluster_labels)
    colors = plt.cm.rainbow(np.linspace(0, 1, len(unique_labels) - (1 if -1 in unique_labels else 0)))
    
    # Plot each cluster with a different color
    color_idx = 0
    for label in unique_labels:
        if label == -1:
            # Noise points in black
            color = 'k'
            marker = 'x'
        else:
            color = colors[color_idx]
            color_idx += 1
            marker = 'o'
        
        mask = cluster_labels == label
        plt.scatter(
            embeddings_2d[mask, 0],
            embeddings_2d[mask, 1],
            c=[color],
            marker=marker,
            label=f'Cluster {label}' if label != -1 else 'Noise',
            alpha=0.7
        )
    
    plt.title('Sequence Clusters based on Similarity')
    plt.xlabel('UMAP Dimension 1')
    plt.ylabel('UMAP Dimension 2')
    
    # Add legend if there aren't too many clusters
    if len(unique_labels) <= 10:
        plt.legend()
    
    # Save figure
    plt.tight_layout()
    plt.savefig(vis_dir / 'sequence_clusters.png', dpi=300)
    plt.close()
    
    logger.info(f"Sequence cluster visualization saved to {vis_dir / 'sequence_clusters.png'}")


def generate_reports(classification_results=None, annotation_results=None, abundance_results=None, output_dir=None):
    """
Generate HTML report with visualizations.
    
Args:
    classification_results: Path to classification results or results object
    annotation_results: Path to annotation results or results object
    abundance_results: Path to abundance results or results object
    output_dir: Directory to save report
    """
    logger.info("Generating reports and visualizations")
    
    if output_dir is None:
        raise ValueError("Output directory must be provided")
    
    output_dir = Path(output_dir)
    vis_dir = output_dir / 'visualizations'
    vis_dir.mkdir(exist_ok=True)
    
    # Generate visualizations based on available results
    if classification_results is not None:
        # If a path was provided, try to infer where the embedding visualization was saved
        embedding_vis_path = None
        if isinstance(classification_results, (str, Path)):
            try:
                # Primary: same directory as the classification results file
                cls_path = Path(classification_results)
                candidate = cls_path.parent / 'embedding_visualization.pkl'
                if candidate.exists():
                    embedding_vis_path = candidate
            except Exception:
                pass

        # Fallback: look in the provided output_dir
        if embedding_vis_path is None:
            candidate = output_dir / 'embedding_visualization.pkl'
            if candidate.exists():
                embedding_vis_path = candidate

        # If found, load and plot
        if embedding_vis_path and Path(embedding_vis_path).exists():
            visualization_data = load_results(embedding_vis_path)
            plot_sequence_clusters(visualization_data, output_dir)
    
    # Generate HTML report
    report_path = output_dir / 'report.html'
    with open(report_path, 'w') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Deep Sea eDNA Analysis Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #2c3e50; }
        h2 { color: #3498db; }
        .section { margin-bottom: 30px; }
        .figure { margin: 10px 0; text-align: center; }
        .figure img { max-width: 100%; border: 1px solid #ddd; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>Deep Sea eDNA Analysis Report</h1>
    <div class="section">
        <h2>Overview</h2>
        <p>This report summarizes the results of the Deep Sea eDNA Analysis Pipeline.</p>
    </div>
""")
        
        # Add classification section if available
        if classification_results is not None:
            f.write("""    <div class="section">
        <h2>Sequence Classification</h2>
        <p>Sequences were clustered based on their similarity using deep learning embeddings.</p>
        <div class="figure">
            <img src="visualizations/sequence_clusters.png" alt="Sequence Clusters">
            <p>Figure 1: Sequence clusters based on similarity.</p>
        </div>
    </div>
""")
        
        # Close HTML
        f.write("""</body>
</html>
""")
    
    logger.info(f"Report generated at {report_path}")
    return report_path


if __name__ == "__main__":
    # This allows the module to be run as a standalone script for testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate visualizations and reports')
    parser.add_argument('--classification', '-c', help='Path to classification results')
    parser.add_argument('--annotation', '-a', help='Path to annotation results')
    parser.add_argument('--abundance', '-b', help='Path to abundance results')
    parser.add_argument('--output', '-o', required=True, help='Output directory')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Generate reports
    generate_reports(
        classification_results=args.classification,
        annotation_results=args.annotation,
        abundance_results=args.abundance,
        output_dir=args.output
    )