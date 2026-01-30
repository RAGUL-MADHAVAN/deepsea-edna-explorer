#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepSeaEDNA: AI-Driven Pipeline for Deep-Sea Environmental DNA Analysis

This is the main pipeline script that orchestrates the entire workflow for
processing and analyzing environmental DNA (eDNA) from deep-sea ecosystems.

The pipeline integrates several components:
1. Sequence preprocessing and quality control (fastp)
2. Deep learning-based sequence classification (DNABERT-2)
3. Unsupervised Clustering & Novelty Discovery (HDBSCAN)
4. Taxonomic annotation (BLAST)
5. Abundance estimation and biodiversity assessment

Usage:
    python pipeline.py --input <input_file> --output <output_dir> [options]
"""

import os
import sys
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Import pipeline modules
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline.manager import PipelineManager

def setup_logging(output_dir):
    """Set up logging configuration."""
    log_dir = os.path.join(output_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'pipeline_{timestamp}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('DeepSeaEDNA')


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='DeepSeaEDNA: AI-Driven Pipeline for Deep-Sea Environmental DNA Analysis'
    )
    
    parser.add_argument('--input', '-i', required=True,
                        help='Input file or directory containing raw eDNA sequences')
    parser.add_argument('--output', '-o', required=True,
                        help='Output directory for results')
    parser.add_argument('--threads', '-t', type=int, default=os.cpu_count(),
                        help='Number of CPU threads to use')
    parser.add_argument('--gpu', action='store_true',
                        help='Use GPU acceleration if available')
    parser.add_argument('--reference-db', '-r',
                        help='Optional reference database for hybrid classification')
    parser.add_argument('--blast-db',
                        help='Path/prefix to a local BLAST nucleotide database (e.g., NCBI nt). If omitted, pipeline uses remote NCBI BLAST for representative sequences (slower).')
    parser.add_argument('--data-type', choices=['amplicon', 'shotgun'], default='amplicon',
                        help='Type of sequencing data: amplicon (default) or shotgun')
    
    return parser.parse_args()


def validate_inputs(args, logger):
    """Validate input parameters and files."""
    # Check if input exists
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input path does not exist: {args.input}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    return input_path, output_path


def run_pipeline(args, logger):
    """Execute the complete eDNA analysis pipeline."""
    start_time = time.time()
    
    # Validate inputs
    input_path, output_path = validate_inputs(args, logger)
    logger.info(f"Starting DeepSeaEDNA pipeline on {input_path}")
    
    # Initialize Pipeline Manager
    manager = PipelineManager(output_path, use_gpu=args.gpu, taxonomy_db_path=args.blast_db)
    
    try:
        # Run the full pipeline
        final_csv, clustering_df, cluster_stats = manager.run(input_path, data_type=args.data_type)
        
        logger.info(f"Pipeline execution successful.")
        logger.info(f"Final results: {final_csv}")
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise
    
    # Calculate execution time
    execution_time = time.time() - start_time
    logger.info(f"Pipeline completed in {execution_time:.2f} seconds")
    
    return output_path


def main():
    """Main function to run the pipeline."""
    # Parse arguments
    args = parse_arguments()
    
    # Set up logging
    logger = setup_logging(args.output)
    
    try:
        # Run the pipeline
        results_dir = run_pipeline(args, logger)
        logger.info(f"Results available in: {results_dir}")
        return 0
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
