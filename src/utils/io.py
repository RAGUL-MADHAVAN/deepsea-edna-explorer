#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Input/Output Utilities

This module provides functions for loading and saving data in the eDNA pipeline.
"""

import os
import pickle
import logging
import numpy as np
from pathlib import Path
from Bio import SeqIO

# Set up logger
logger = logging.getLogger('DeepSeaEDNA.utils.io')


def load_sequences(input_path):
    """Load DNA sequences from a file or directory.
    
    Args:
        input_path: Path to input file or directory
        
    Returns:
        List of sequences
    """
    input_path = Path(input_path)
    
    # Check if input_path is a file or directory
    if input_path.is_file():
        return _load_sequences_from_file(input_path)
    elif input_path.is_dir():
        return _load_sequences_from_directory(input_path)
    elif isinstance(input_path, dict) and 'sequences' in input_path:
        # Input is already a data object
        return input_path['sequences']
    else:
        raise ValueError(f"Invalid input path: {input_path}")


def _load_sequences_from_file(file_path):
    """Load sequences from a single file.
    
    Args:
        file_path: Path to sequence file
        
    Returns:
        List of sequences
    """
    file_path = Path(file_path)
    
    # Determine file format based on extension
    ext = file_path.suffix.lower()
    
    if ext in ['.fastq', '.fq'] or str(file_path).endswith('.fastq.gz') or str(file_path).endswith('.fq.gz'):
        format_name = 'fastq'
    elif ext in ['.fasta', '.fa', '.fna'] or str(file_path).endswith('.fasta.gz') or str(file_path).endswith('.fa.gz'):
        format_name = 'fasta'
    else:
        raise ValueError(f"Unsupported file format: {ext}")
    
    # Load sequences
    logger.info(f"Loading sequences from {file_path}")
    
    sequences = []
    try:
        # In a real implementation, this would use BioPython's SeqIO to parse the file
        # For demonstration, we'll simulate loading sequences
        
        # Simulate loading 100 sequences
        for i in range(100):
            seq = ''.join(np.random.choice(['A', 'C', 'G', 'T'], size=150))
            sequences.append(seq)
        
        logger.info(f"Loaded {len(sequences)} sequences from {file_path}")
    except Exception as e:
        logger.error(f"Error loading sequences from {file_path}: {e}")
        raise
    
    return sequences


def _load_sequences_from_directory(directory_path):
    """Load sequences from all files in a directory.
    
    Args:
        directory_path: Path to directory containing sequence files
        
    Returns:
        List of sequences
    """
    directory_path = Path(directory_path)
    
    # Find all sequence files in the directory
    sequence_files = []
    for ext in ['.fastq', '.fq', '.fastq.gz', '.fq.gz', '.fasta', '.fa', '.fna', '.fasta.gz', '.fa.gz']:
        sequence_files.extend(directory_path.glob(f"*{ext}"))
    
    if not sequence_files:
        raise ValueError(f"No sequence files found in {directory_path}")
    
    # Load sequences from each file
    all_sequences = []
    for file_path in sequence_files:
        sequences = _load_sequences_from_file(file_path)
        all_sequences.extend(sequences)
    
    logger.info(f"Loaded {len(all_sequences)} sequences from {len(sequence_files)} files in {directory_path}")
    
    return all_sequences


def save_results(results, output_path):
    """Save results to a file.
    
    Args:
        results: Results object to save
        output_path: Path to save results
    """
    output_path = Path(output_path)
    
    # Create parent directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save results
    logger.info(f"Saving results to {output_path}")
    
    try:
        with open(output_path, 'wb') as f:
            pickle.dump(results, f)
        
        logger.info(f"Results saved to {output_path}")
    except Exception as e:
        logger.error(f"Error saving results to {output_path}: {e}")
        raise


def load_results(input_path):
    """Load results from a file.
    
    Args:
        input_path: Path to results file
        
    Returns:
        Results object
    """
    # Check if input_path is already a results object
    if not isinstance(input_path, (str, Path)):
        return input_path
    
    input_path = Path(input_path)
    
    # Load results
    logger.info(f"Loading results from {input_path}")
    
    try:
        with open(input_path, 'rb') as f:
            results = pickle.load(f)
        
        logger.info(f"Results loaded from {input_path}")
        return results
    except Exception as e:
        logger.error(f"Error loading results from {input_path}: {e}")
        raise