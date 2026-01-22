#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Abundance Estimation Module

This module implements abundance estimation for eDNA sequences to quantify
the relative abundance of different taxa in environmental samples.

The module includes:
1. Read count normalization
2. Relative abundance calculation
3. Diversity metrics computation
4. Statistical analysis of community structure
"""

import os
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from sklearn.preprocessing import normalize

# Local imports
from src.utils.io import save_results, load_results

# Set up logger
logger = logging.getLogger('DeepSeaEDNA.abundance')


class AbundanceEstimator:
    """Estimator for taxon abundance in eDNA samples."""
    
    def __init__(self):
        """Initialize the abundance estimator."""
        pass
    
    def normalize_read_counts(self, annotations, sequences):
        """Normalize read counts for abundance estimation.
        
        Args:
            annotations: DataFrame with taxonomic annotations
            sequences: List of sequences
            
        Returns:
            DataFrame with normalized read counts
        """
        logger.info("Normalizing read counts")
        
        # Count sequences per taxon at each level
        tax_levels = ['kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species']
        
        # Initialize results dictionary
        abundance_data = {}
        
        for level in tax_levels:
            if level in annotations.columns:
                logger.info(f"Calculating abundance for {level}")
                
                # Group by taxon and count sequences
                taxon_counts = annotations.groupby(level).size().reset_index(name='count')
                
                # Calculate relative abundance
                total_sequences = len(sequences)
                taxon_counts['relative_abundance'] = taxon_counts['count'] / total_sequences
                
                # Store in results
                abundance_data[level] = taxon_counts
        
        return abundance_data
    
    def calculate_diversity_metrics(self, abundance_data):
        """Calculate diversity metrics for the community.
        
        Args:
            abundance_data: Dictionary with abundance data for each taxonomic level
            
        Returns:
            Dictionary with diversity metrics
        """
        logger.info("Calculating diversity metrics")
        
        diversity_metrics = {}
        
        for level, data in abundance_data.items():
            # Extract abundance values
            abundances = data['relative_abundance'].values
            
            # Shannon diversity index
            shannon = -np.sum(abundances * np.log(abundances + 1e-10))
            
            # Simpson diversity index
            simpson = 1 - np.sum(abundances ** 2)
            
            # Species richness
            richness = len(data)
            
            # Pielou's evenness
            evenness = shannon / np.log(richness) if richness > 1 else 0
            
            # Store metrics
            diversity_metrics[level] = {
                'shannon_index': shannon,
                'simpson_index': simpson,
                'richness': richness,
                'evenness': evenness
            }
        
        return diversity_metrics
    
    def detect_differential_abundance(self, annotations, sample_metadata=None):
        """Detect differentially abundant taxa between sample groups.
        
        Args:
            annotations: DataFrame with taxonomic annotations
            sample_metadata: Optional DataFrame with sample metadata for group comparisons
            
        Returns:
            DataFrame with differential abundance results
        """
        logger.info("Detecting differentially abundant taxa")
        
        # If no sample metadata is provided, we can't do differential abundance analysis
        if sample_metadata is None:
            logger.warning("No sample metadata provided, skipping differential abundance analysis")
            return None
        
        # In a real implementation, this would perform statistical tests
        # between sample groups to identify differentially abundant taxa
        # For now, we'll return a placeholder result
        
        differential_results = pd.DataFrame({
            'taxon': ['Taxon_A', 'Taxon_B', 'Taxon_C'],
            'log2_fold_change': [2.5, -1.8, 3.2],
            'p_value': [0.001, 0.02, 0.005],
            'adjusted_p_value': [0.003, 0.04, 0.01]
        })
        
        return differential_results
    
    def estimate_abundance(self, annotations, sequences, sample_metadata=None):
        """Estimate abundance and calculate diversity metrics.
        
        Args:
            annotations: DataFrame with taxonomic annotations
            sequences: List of sequences
            sample_metadata: Optional DataFrame with sample metadata
            
        Returns:
            Dictionary with abundance results
        """
        # Normalize read counts
        abundance_data = self.normalize_read_counts(annotations, sequences)
        
        # Calculate diversity metrics
        diversity_metrics = self.calculate_diversity_metrics(abundance_data)
        
        # Detect differential abundance if sample metadata is provided
        differential_abundance = None
        if sample_metadata is not None:
            differential_abundance = self.detect_differential_abundance(annotations, sample_metadata)
        
        # Combine results
        abundance_results = {
            'abundance_data': abundance_data,
            'diversity_metrics': diversity_metrics,
            'differential_abundance': differential_abundance
        }
        
        return abundance_results


def run_abundance_estimation(input_data, output_dir, threads=1):
    """Run the abundance estimation pipeline.
    
    Args:
        input_data: Path to annotation results or annotation data object
        output_dir: Directory to save results
        threads: Number of CPU threads to use
    
    Returns:
        Path to abundance results
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Load annotation results
    logger.info("Loading annotation results for abundance estimation")
    annotation_data = load_results(input_data)
    
    sequences = annotation_data['sequences']
    annotations = annotation_data['annotations']
    
    # Initialize abundance estimator
    estimator = AbundanceEstimator()
    
    # Estimate abundance
    abundance_results = estimator.estimate_abundance(annotations, sequences)
    
    # Save abundance results
    results_path = output_dir / 'abundance_results.pkl'
    save_results(abundance_results, results_path)
    
    # Save abundance data as CSV for easy viewing
    for level, data in abundance_results['abundance_data'].items():
        csv_path = output_dir / f'abundance_{level}.csv'
        data.to_csv(csv_path, index=False)
    
    # Save diversity metrics as CSV
    diversity_df = pd.DataFrame(abundance_results['diversity_metrics']).T
    diversity_csv_path = output_dir / 'diversity_metrics.csv'
    diversity_df.to_csv(diversity_csv_path)
    
    logger.info(f"Abundance results saved to {results_path}")
    logger.info(f"Diversity metrics saved to {diversity_csv_path}")
    
    return results_path


if __name__ == "__main__":
    # This allows the module to be run as a standalone script for testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Run abundance estimation')
    parser.add_argument('--input', '-i', required=True, help='Input annotation results')
    parser.add_argument('--output', '-o', required=True, help='Output directory')
    parser.add_argument('--threads', '-t', type=int, default=1, help='Number of CPU threads')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run abundance estimation
    run_abundance_estimation(args.input, args.output, threads=args.threads)