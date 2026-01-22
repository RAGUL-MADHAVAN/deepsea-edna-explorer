#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Preprocessing Utilities

This module provides functions for preprocessing DNA sequences in the eDNA pipeline.
"""

import logging
import numpy as np
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

# Set up logger
logger = logging.getLogger('DeepSeaEDNA.utils.preprocessing')


def preprocess_sequences(input_path, output_dir, min_quality=40, min_length=100, threads=1):
    """Preprocess raw sequences for analysis.
    
    Args:
        input_path: Path to input sequences
        output_dir: Directory to save preprocessed sequences
        min_quality: Minimum quality score for filtering
        min_length: Minimum sequence length after filtering
        threads: Number of CPU threads to use
        
    Returns:
        Path to preprocessed sequences
    """
    from src.utils.io import load_sequences, save_results
    
    logger.info("Preprocessing sequences")
    logger.info(f"Quality threshold: {min_quality}, Length threshold: {min_length}")
    
    # Load sequences
    sequences = load_sequences(input_path)
    
    # Filter sequences by quality and length
    filtered_sequences = filter_sequences(sequences, min_quality, min_length)
    
    # Save preprocessed sequences
    preprocessed_data = {
        'sequences': filtered_sequences,
        'preprocessing_stats': {
            'input_sequences': len(sequences),
            'filtered_sequences': len(filtered_sequences),
            'min_quality': min_quality,
            'min_length': min_length
        }
    }
    
    output_path = output_dir / 'preprocessed_sequences.pkl'
    save_results(preprocessed_data, output_path)
    
    logger.info(f"Preprocessed {len(sequences)} sequences, kept {len(filtered_sequences)}")
    
    return output_path


def filter_sequences(sequences, min_quality=40, min_length=100):
    """Filter sequences by quality and length.
    
    Args:
        sequences: List of sequences
        min_quality: Minimum quality score
        min_length: Minimum sequence length
        
    Returns:
        List of filtered sequences
    """
    # In a real implementation, this would use quality scores from FASTQ files
    # For demonstration, we'll simulate quality filtering
    
    filtered_sequences = []
    for seq in sequences:
        # Check sequence length
        if len(seq) >= min_length:
            # Simulate quality check (in reality, would use quality scores from FASTQ)
            # For demonstration, we'll randomly keep 90% of sequences
            if np.random.random() < 0.9:
                filtered_sequences.append(seq)
    
    return filtered_sequences


def encode_sequences(sequences, max_length=1000):
    """Encode DNA sequences as one-hot vectors.
    
    Args:
        sequences: List of DNA sequences
        max_length: Maximum sequence length (sequences will be padded/truncated)
        
    Returns:
        Numpy array of one-hot encoded sequences
    """
    # Define nucleotide mapping
    nucleotide_map = {'A': 0, 'C': 1, 'G': 2, 'T': 3, 'N': 4}
    
    # Initialize encoded sequences array
    n_sequences = len(sequences)
    encoded_sequences = np.zeros((n_sequences, 5, max_length), dtype=np.float32)
    
    # Encode each sequence
    for i, seq in enumerate(sequences):
        # Truncate or pad sequence
        if len(seq) > max_length:
            seq = seq[:max_length]
        
        # One-hot encode sequence
        for j, nucleotide in enumerate(seq):
            if j < max_length:
                nucleotide = nucleotide.upper()
                if nucleotide in nucleotide_map:
                    encoded_sequences[i, nucleotide_map[nucleotide], j] = 1.0
                else:
                    # Unknown nucleotide, encode as N
                    encoded_sequences[i, 4, j] = 1.0
    
    return encoded_sequences


def reverse_complement(sequences):
    """Generate reverse complement of DNA sequences.
    
    Args:
        sequences: List of DNA sequences
        
    Returns:
        List of reverse complemented sequences
    """
    # In a real implementation, this would use BioPython's Seq.reverse_complement()
    # For demonstration, we'll implement a simple version
    
    complement_map = {'A': 'T', 'C': 'G', 'G': 'C', 'T': 'A', 'N': 'N'}
    
    reverse_complemented = []
    for seq in sequences:
        rev_comp = ''.join(complement_map.get(nucleotide.upper(), 'N') for nucleotide in reversed(seq))
        reverse_complemented.append(rev_comp)
    
    return reverse_complemented


def generate_kmers(sequences, k=6):
    """Generate k-mers from sequences.
    
    Args:
        sequences: List of DNA sequences
        k: k-mer length
        
    Returns:
        Dictionary mapping sequences to their k-mer counts
    """
    kmer_counts = {}
    
    for i, seq in enumerate(sequences):
        kmer_counts[i] = {}
        
        # Generate k-mers
        for j in range(len(seq) - k + 1):
            kmer = seq[j:j+k]
            
            # Skip k-mers with ambiguous nucleotides
            if 'N' in kmer:
                continue
            
            # Count k-mer
            if kmer in kmer_counts[i]:
                kmer_counts[i][kmer] += 1
            else:
                kmer_counts[i][kmer] = 1
    
    return kmer_counts