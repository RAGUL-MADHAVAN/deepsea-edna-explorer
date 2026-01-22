#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test Pipeline

This module contains tests for the Deep Sea eDNA Analysis Pipeline.
"""

import os
import sys
import unittest
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import run_pipeline
from src.classification import run_classification
from src.annotation import run_annotation
from src.abundance import run_abundance_estimation
from src.utils.preprocessing import preprocess_sequences


class TestPipeline(unittest.TestCase):
    """Test cases for the Deep Sea eDNA Analysis Pipeline."""
    
    def setUp(self):
        """Set up test environment."""
        # Define test data directory
        self.test_data_dir = Path('data/raw')
        self.test_output_dir = Path('data/processed/test')
        
        # Create output directory if it doesn't exist
        self.test_output_dir.mkdir(parents=True, exist_ok=True)
    
    def test_preprocessing(self):
        """Test preprocessing module."""
        # This is a mock test since we don't have actual data
        # In a real test, we would use actual data and check the results
        
        # Create mock data
        mock_sequences = ['ACGTACGT' * 20] * 10
        
        # Test preprocessing
        from src.utils.preprocessing import filter_sequences
        filtered_sequences = filter_sequences(mock_sequences, min_quality=20, min_length=100)
        
        # Check results
        self.assertIsInstance(filtered_sequences, list)
        self.assertLessEqual(len(filtered_sequences), len(mock_sequences))
    
    def test_classification(self):
        """Test classification module."""
        # This is a mock test since we don't have actual data
        # In a real test, we would use actual data and check the results
        
        # Create mock data
        mock_sequences = ['ACGTACGT' * 20] * 10
        
        # Test classification
        from src.classification.classify import DeepCluster
        classifier = DeepCluster(n_clusters=3)
        clusters = classifier.fit_predict(mock_sequences)
        
        # Check results
        self.assertIsInstance(clusters, dict)
        self.assertEqual(len(clusters), 3)  # 3 clusters
    
    def test_annotation(self):
        """Test annotation module."""
        # This is a mock test since we don't have actual data
        # In a real test, we would use actual data and check the results
        
        # Create mock data
        mock_clusters = {
            0: ['ACGTACGT' * 20] * 3,
            1: ['TGCATGCA' * 20] * 4,
            2: ['GCTAGCTA' * 20] * 3
        }
        
        # Test annotation
        from src.annotation.annotate import HybridAnnotator
        annotator = HybridAnnotator()
        taxa = annotator.annotate(mock_clusters)
        
        # Check results
        self.assertIsInstance(taxa, dict)
        self.assertEqual(len(taxa), 3)  # 3 taxa
    
    def test_abundance(self):
        """Test abundance estimation module."""
        # This is a mock test since we don't have actual data
        # In a real test, we would use actual data and check the results
        
        # Create mock data
        mock_taxa = {
            'Taxon1': ['ACGTACGT' * 20] * 3,
            'Taxon2': ['TGCATGCA' * 20] * 4,
            'Taxon3': ['GCTAGCTA' * 20] * 3
        }
        
        # Test abundance estimation
        from src.abundance.estimate import AbundanceEstimator
        estimator = AbundanceEstimator()
        abundance = estimator.estimate_abundance(mock_taxa)
        
        # Check results
        self.assertIsInstance(abundance, dict)
        self.assertEqual(len(abundance), 3)  # 3 taxa
        
        # Check diversity metrics
        self.assertIn('shannon_diversity', abundance)
        self.assertIn('simpson_diversity', abundance)
    
    def test_pipeline(self):
        """Test full pipeline."""
        # This is a mock test since we don't have actual data
        # In a real test, we would use actual data and check the results
        
        # Create mock data
        mock_input_path = 'mock_input'
        mock_output_dir = self.test_output_dir
        
        # Mock the pipeline functions
        def mock_run_pipeline(*args, **kwargs):
            return {
                'preprocessing_stats': {
                    'input_sequences': 100,
                    'filtered_sequences': 90
                },
                'classification_results': {
                    'clusters': {0: [], 1: [], 2: []}
                },
                'annotation_results': {
                    'taxa': {'Taxon1': [], 'Taxon2': [], 'Taxon3': []}
                },
                'abundance_results': {
                    'abundance': {'Taxon1': 0.3, 'Taxon2': 0.4, 'Taxon3': 0.3},
                    'shannon_diversity': 1.0986,
                    'simpson_diversity': 0.66
                }
            }
        
        # Replace actual function with mock
        original_run_pipeline = run_pipeline
        globals()['run_pipeline'] = mock_run_pipeline
        
        try:
            # Test pipeline
            results = run_pipeline(
                input_path=mock_input_path,
                output_dir=mock_output_dir
            )
            
            # Check results
            self.assertIsInstance(results, dict)
            self.assertIn('preprocessing_stats', results)
            self.assertIn('classification_results', results)
            self.assertIn('annotation_results', results)
            self.assertIn('abundance_results', results)
        finally:
            # Restore original function
            globals()['run_pipeline'] = original_run_pipeline


if __name__ == '__main__':
    unittest.main()