#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepSeaEDNA: AI-Driven Pipeline for Deep-Sea Environmental DNA Analysis

This is the main pipeline script that orchestrates the entire workflow for
processing and analyzing environmental DNA (eDNA) from deep-sea ecosystems.

The pipeline integrates several components:
1. Sequence preprocessing and quality control
2. Deep learning-based sequence classification
3. Taxonomic annotation using hybrid approaches
4. Abundance estimation and biodiversity assessment

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
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.classification import classify
from src.annotation import annotate
from src.abundance import estimate
from src.utils import io, preprocessing, visualization, mock_bio


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
    parser.add_argument('--min-quality', type=int, default=20,
                        help='Minimum quality score for sequence filtering')
    parser.add_argument('--min-length', type=int, default=100,
                        help='Minimum sequence length after quality filtering')
    parser.add_argument('--skip-steps', nargs='+', choices=['classification', 'annotation', 'abundance'],
                        help='Skip specific pipeline steps')
    parser.add_argument('--config', '-c',
                        help='Configuration file with pipeline parameters')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    
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
    
    # Check reference database if provided
    if args.reference_db and not Path(args.reference_db).exists():
        logger.error(f"Reference database does not exist: {args.reference_db}")
        sys.exit(1)
    
    # Check if input is in the correct format
    allowed_exts = ['.fastq', '.fq', '.fastq.gz', '.fq.gz', '.fasta', '.fa', '.fna', '.fasta.gz', '.fa.gz']
    if input_path.is_file() and not any(input_path.name.endswith(ext) for ext in allowed_exts):
        logger.warning(f"Input file may not be in FASTQ/FASTA format: {args.input}")
    
    return input_path, output_path


def run_pipeline(args, logger):
    """Execute the complete eDNA analysis pipeline."""
    start_time = time.time()
    
    # Validate inputs
    input_path, output_path = validate_inputs(args, logger)
    logger.info(f"Starting DeepSeaEDNA pipeline on {input_path}")
    
    # Create directories for intermediate results
    preproc_dir = output_path / 'preprocessed'
    classified_dir = output_path / 'classified'
    annotated_dir = output_path / 'annotated'
    abundance_dir = output_path / 'abundance'
    results_dir = output_path / 'results'
    
    for directory in [preproc_dir, classified_dir, annotated_dir, abundance_dir, results_dir]:
        directory.mkdir(exist_ok=True)
    
    # Step 1: Preprocessing
    logger.info("Step 1: Preprocessing and quality control")
    preprocessed_data = preprocessing.preprocess_sequences(
        input_path=input_path,
        output_dir=preproc_dir,
        min_quality=args.min_quality,
        min_length=args.min_length,
        threads=args.threads
    )

    preproc_payload = io.load_results(preprocessed_data)
    sequences = preproc_payload.get('sequences', [])

    # Step 2: HMM marker detection (simulated)
    logger.info("Step 2: HMM marker/eukaryote detection (simulated demo)")
    hmm_results = mock_bio.simulate_hmm_marker_detection(sequences, preproc_dir)
    logger.info(
        "HMM demo summary: %s markers, avg_score=%s",
        len(hmm_results.get('summary', {}).get('markers_detected', [])),
        hmm_results.get('summary', {}).get('avg_hmm_score')
    )

    # Step 3: BLAST similarity search (simulated)
    logger.info("Step 3: BLAST similarity search (simulated demo)")
    blast_results = mock_bio.simulate_blast_similarity(sequences, preproc_dir)
    logger.info(
        "BLAST demo summary: %s sequences, unique_hits=%s",
        blast_results.get('total_sequences'),
        len({h.get('top_hit') for h in blast_results.get('top_hits', [])})
    )
    
    # Step 4: Sequence Classification / Embedding
    if 'classification' not in (args.skip_steps or []):
        logger.info("Step 4: Deep learning sequence embedding + clustering")
        classification_results = classify.run_classification(
            input_data=preprocessed_data,
            output_dir=classified_dir,
            reference_db=args.reference_db,
            use_gpu=args.gpu,
            threads=args.threads
        )
    else:
        logger.info("Skipping classification step")
        classification_results = preprocessed_data  # Pass through
    
    # Step 5: Taxonomic Annotation
    if 'annotation' not in (args.skip_steps or []):
        logger.info("Step 5: Taxonomic annotation (hybrid + simulated BLAST/HMM)"
                    "")
        annotation_results = annotate.run_annotation(
            input_data=classification_results,
            output_dir=annotated_dir,
            reference_db=args.reference_db,
            use_gpu=args.gpu,
            threads=args.threads
        )
    else:
        logger.info("Skipping annotation step")
        annotation_results = classification_results  # Pass through
    
    # Step 6: Abundance Estimation
    if 'abundance' not in (args.skip_steps or []):
        logger.info("Step 6: Abundance estimation and biodiversity assessment")
        abundance_results = estimate.run_abundance_estimation(
            input_data=annotation_results,
            output_dir=abundance_dir,
            threads=args.threads
        )
    else:
        logger.info("Skipping abundance estimation step")
        abundance_results = annotation_results  # Pass through
    
    # Generate final reports and visualizations
    logger.info("Step 7: Generating final reports and visualizations")
    visualization.generate_reports(
        classification_results=classification_results if 'classification' not in (args.skip_steps or []) else None,
        annotation_results=annotation_results if 'annotation' not in (args.skip_steps or []) else None,
        abundance_results=abundance_results if 'abundance' not in (args.skip_steps or []) else None,
        output_dir=results_dir
    )
    
    # Calculate execution time
    execution_time = time.time() - start_time
    logger.info(f"Pipeline completed in {execution_time:.2f} seconds")
    
    return results_dir


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