#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Taxonomic Annotation Module

This module implements taxonomic annotation for eDNA sequences using a hybrid approach
that combines reference-based and reference-free methods to overcome the limitations
of incomplete reference databases for deep-sea organisms.

The module includes:
1. Reference-based annotation using available databases
2. Reference-free annotation using sequence characteristics
3. Confidence scoring for taxonomic assignments
4. Novel taxa identification
"""

import os
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import torch
import torch.nn as nn

# Local imports
from src.utils.io import save_results, load_results

# Set up logger
logger = logging.getLogger('DeepSeaEDNA.annotation')


class TaxonomicClassifier(nn.Module):
    """Neural network for taxonomic classification."""
    
    def __init__(self, embedding_dim=128, hidden_dims=[256, 128], num_taxa=100):
        """Initialize the taxonomic classifier.
        
        Args:
            embedding_dim: Dimension of input sequence embeddings
            hidden_dims: List of hidden layer dimensions
            num_taxa: Number of taxonomic classes to predict
        """
        super(TaxonomicClassifier, self).__init__()
        
        # Build classifier layers
        layers = []
        prev_dim = embedding_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            prev_dim = hidden_dim
        
        self.feature_extractor = nn.Sequential(*layers)
        self.classifier = nn.Linear(prev_dim, num_taxa)
        
    def forward(self, x):
        """Forward pass through the network.
        
        Args:
            x: Input tensor of sequence embeddings
            
        Returns:
            Logits for taxonomic classes
        """
        features = self.feature_extractor(x)
        logits = self.classifier(features)
        return logits


class HybridAnnotator:
    """Hybrid approach for taxonomic annotation."""
    
    def __init__(self, reference_db=None, use_gpu=False):
        """Initialize the hybrid annotator.
        
        Args:
            reference_db: Path to reference database (if available)
            use_gpu: Whether to use GPU acceleration
        """
        self.reference_db = reference_db
        self.device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
        self.has_reference = reference_db is not None
        
        # Taxonomic levels
        self.tax_levels = ['kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species']
        
        # Initialize classifiers for each taxonomic level
        self.classifiers = {}
        self.taxa_maps = {}
        
        # Load reference database if available
        if self.has_reference:
            self._load_reference_db()
    
    def _load_reference_db(self):
        """Load reference database for annotation."""
        logger.info(f"Loading reference database from {self.reference_db}")
        
        # In a real implementation, this would load actual reference data
        # For now, we'll simulate it with placeholder data
        
        # Simulate reference taxa for each level
        for level in self.tax_levels:
            # In a real implementation, this would be loaded from files
            self.taxa_maps[level] = {i: f"Taxon_{level}_{i}" for i in range(20)}
    
    def train_classifiers(self, embeddings, reference_labels=None):
        """Train taxonomic classifiers.
        
        Args:
            embeddings: Sequence embeddings
            reference_labels: Known taxonomic labels (if available)
        """
        logger.info("Training taxonomic classifiers")
        
        # If we have reference labels, use supervised learning
        if self.has_reference and reference_labels is not None:
            self._train_supervised(embeddings, reference_labels)
        else:
            # Otherwise, use unsupervised approach based on clusters
            self._train_unsupervised(embeddings)
    
    def _train_supervised(self, embeddings, reference_labels):
        """Train classifiers using supervised learning with reference labels.
        
        Args:
            embeddings: Sequence embeddings
            reference_labels: Known taxonomic labels
        """
        logger.info("Training supervised taxonomic classifiers")
        
        for level in self.tax_levels:
            if level in reference_labels.columns:
                logger.info(f"Training classifier for {level}")
                
                # Get labels for this taxonomic level
                y = reference_labels[level].values
                
                # Split data
                X_train, X_val, y_train, y_val = train_test_split(
                    embeddings, y, test_size=0.2, random_state=42
                )
                
                # Convert to PyTorch tensors
                X_train = torch.tensor(X_train, dtype=torch.float32)
                y_train = torch.tensor(y_train, dtype=torch.long)
                X_val = torch.tensor(X_val, dtype=torch.float32)
                y_val = torch.tensor(y_val, dtype=torch.long)
                
                # Create classifier
                num_taxa = len(np.unique(y))
                classifier = TaxonomicClassifier(num_taxa=num_taxa)
                classifier.to(self.device)
                
                # Train classifier
                self._train_classifier(classifier, X_train, y_train, X_val, y_val)
                
                # Save classifier
                self.classifiers[level] = classifier
    
    def _train_unsupervised(self, embeddings):
        """Train classifiers using unsupervised learning based on clusters.
        
        Args:
            embeddings: Sequence embeddings
        """
        logger.info("Training unsupervised taxonomic classifiers")
        
        # In a real implementation, this would use more sophisticated techniques
        # For now, we'll use a simple random forest classifier on cluster assignments
        
        # Use random forest for each taxonomic level as a placeholder
        for level in self.tax_levels:
            logger.info(f"Training classifier for {level}")
            
            # Simulate cluster assignments as features
            # In a real implementation, these would be derived from the data
            n_samples = embeddings.shape[0]
            n_clusters = min(20, n_samples // 5)  # Arbitrary number of clusters
            
            # Simulate cluster assignments
            cluster_assignments = np.random.randint(0, n_clusters, size=n_samples)
            
            # Train a random forest classifier
            clf = RandomForestClassifier(n_estimators=100, random_state=42)
            clf.fit(embeddings, cluster_assignments)
            
            # Save classifier
            self.classifiers[level] = clf
    
    def _train_classifier(self, model, X_train, y_train, X_val, y_val, epochs=10, lr=0.001):
        """Train a neural network classifier.
        
        Args:
            model: The classifier model
            X_train: Training data
            y_train: Training labels
            X_val: Validation data
            y_val: Validation labels
            epochs: Number of training epochs
            lr: Learning rate
        """
        # Define loss function and optimizer
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        
        # Create data loaders
        train_data = torch.utils.data.TensorDataset(X_train, y_train)
        train_loader = torch.utils.data.DataLoader(train_data, batch_size=32, shuffle=True)
        
        val_data = torch.utils.data.TensorDataset(X_val, y_val)
        val_loader = torch.utils.data.DataLoader(val_data, batch_size=32)
        
        # Training loop
        model.train()
        for epoch in range(epochs):
            total_loss = 0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                
                # Forward pass
                logits = model(X_batch)
                loss = criterion(logits, y_batch)
                
                # Backward pass and optimize
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            # Validation
            model.eval()
            val_loss = 0
            correct = 0
            total = 0
            
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(self.device)
                    y_batch = y_batch.to(self.device)
                    
                    logits = model(X_batch)
                    loss = criterion(logits, y_batch)
                    val_loss += loss.item()
                    
                    _, predicted = torch.max(logits, 1)
                    total += y_batch.size(0)
                    correct += (predicted == y_batch).sum().item()
            
            val_accuracy = correct / total
            logger.info(f"Epoch {epoch+1}/{epochs}, Train Loss: {total_loss/len(train_loader):.4f}, "
                       f"Val Loss: {val_loss/len(val_loader):.4f}, Val Acc: {val_accuracy:.4f}")
            
            model.train()
    
    def annotate_sequences(self, embeddings, cluster_labels):
        """Annotate sequences with taxonomic information.
        
        Args:
            embeddings: Sequence embeddings
            cluster_labels: Cluster assignments for sequences
            
        Returns:
            DataFrame with taxonomic annotations and confidence scores
        """
        logger.info("Annotating sequences with taxonomic information")
        
        n_sequences = len(embeddings)
        
        # Initialize results DataFrame
        results = pd.DataFrame({
            'sequence_id': [f"seq_{i}" for i in range(n_sequences)],
            'cluster': cluster_labels
        })
        
        # Add columns for each taxonomic level
        for level in self.tax_levels:
            results[level] = None
            results[f"{level}_confidence"] = 0.0
        
        # If we have trained classifiers, use them for prediction
        if self.classifiers:
            for level in self.tax_levels:
                if level in self.classifiers:
                    logger.info(f"Predicting {level} annotations")
                    
                    classifier = self.classifiers[level]
                    
                    # Check if it's a PyTorch model or scikit-learn
                    if isinstance(classifier, nn.Module):
                        # PyTorch model
                        classifier.eval()
                        X = torch.tensor(embeddings, dtype=torch.float32).to(self.device)
                        
                        with torch.no_grad():
                            logits = classifier(X)
                            probabilities = torch.softmax(logits, dim=1)
                            
                            # Get predictions and confidence scores
                            predictions = torch.argmax(probabilities, dim=1).cpu().numpy()
                            confidences = torch.max(probabilities, dim=1)[0].cpu().numpy()
                    else:
                        # Scikit-learn model
                        predictions = classifier.predict(embeddings)
                        confidences = np.max(classifier.predict_proba(embeddings), axis=1)
                    
                    # Map numeric predictions to taxon names if available
                    if level in self.taxa_maps:
                        taxa = [self.taxa_maps[level].get(p, f"Unknown_{p}") for p in predictions]
                    else:
                        taxa = [f"Cluster_{p}" for p in predictions]
                    
                    # Update results
                    results[level] = taxa
                    results[f"{level}_confidence"] = confidences
        
        # For levels without classifiers, use cluster-based annotation
        for level in self.tax_levels:
            if level not in self.classifiers:
                # Group by cluster and assign the same taxon to all sequences in a cluster
                for cluster in np.unique(cluster_labels):
                    if cluster == -1:  # Noise points
                        continue
                    
                    # Get indices of sequences in this cluster
                    cluster_indices = np.where(cluster_labels == cluster)[0]
                    
                    # Assign a placeholder taxon name
                    taxon_name = f"Cluster_{cluster}_taxon"
                    
                    # Update results
                    results.loc[cluster_indices, level] = taxon_name
                    results.loc[cluster_indices, f"{level}_confidence"] = 0.5  # Placeholder confidence
        
        # Identify potential novel taxa
        results['is_novel'] = results['species_confidence'] < 0.5
        
        return results


def run_annotation(input_data, output_dir, reference_db=None, use_gpu=False, threads=1):
    """Run the taxonomic annotation pipeline.
    
    Args:
        input_data: Path to classification results or classification data object
        output_dir: Directory to save results
        reference_db: Optional path to reference database
        use_gpu: Whether to use GPU acceleration
        threads: Number of CPU threads to use
    
    Returns:
        Path to annotation results
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Load classification results
    logger.info("Loading classification results for annotation")
    classification_data = load_results(input_data)
    
    sequences = classification_data['sequences']
    embeddings = classification_data['embeddings']
    cluster_labels = classification_data['cluster_labels']
    
    # Initialize annotator
    annotator = HybridAnnotator(reference_db=reference_db, use_gpu=use_gpu)
    
    # Train classifiers
    annotator.train_classifiers(embeddings)
    
    # Annotate sequences
    annotations = annotator.annotate_sequences(embeddings, cluster_labels)
    
    # Save annotation results
    annotation_results = {
        'sequences': sequences,
        'embeddings': embeddings,
        'cluster_labels': cluster_labels,
        'annotations': annotations
    }
    
    results_path = output_dir / 'annotation_results.pkl'
    save_results(annotation_results, results_path)
    
    # Save annotations as CSV for easy viewing
    csv_path = output_dir / 'taxonomic_annotations.csv'
    annotations.to_csv(csv_path, index=False)
    
    logger.info(f"Annotation results saved to {results_path}")
    logger.info(f"Taxonomic annotations saved to {csv_path}")
    
    return results_path


if __name__ == "__main__":
    # This allows the module to be run as a standalone script for testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Run taxonomic annotation')
    parser.add_argument('--input', '-i', required=True, help='Input classification results')
    parser.add_argument('--output', '-o', required=True, help='Output directory')
    parser.add_argument('--reference', '-r', help='Reference database')
    parser.add_argument('--gpu', action='store_true', help='Use GPU acceleration')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run annotation
    run_annotation(args.input, args.output, reference_db=args.reference, use_gpu=args.gpu)