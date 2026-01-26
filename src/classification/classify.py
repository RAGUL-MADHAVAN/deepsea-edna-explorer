#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Deep Learning-based Sequence Classification Module

This module implements sequence classification using deep learning approaches
to identify patterns in eDNA sequences without heavy reliance on reference databases.

The module includes:
1. Sequence embedding generation
2. Unsupervised clustering
3. Neural network classification
4. Hybrid classification (combining reference-free and reference-based approaches)
"""

import os
import logging
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from pathlib import Path
from sklearn.cluster import DBSCAN
from sklearn.manifold import TSNE
from umap import UMAP
import hdbscan

# Local imports
from src.utils.io import save_results, load_sequences, load_results
from src.utils.preprocessing import encode_sequences

# Set up logger
logger = logging.getLogger('DeepSeaEDNA.classification')


class SequenceEmbedder(nn.Module):
    """Neural network for generating sequence embeddings."""
    
    def __init__(self, input_dim=5, hidden_dims=[128, 256, 512], embedding_dim=128):
        """Initialize the sequence embedder.
        
        Args:
            input_dim: Dimension of input features (5 for one-hot encoded A,C,G,T,N)
            hidden_dims: List of hidden layer dimensions
            embedding_dim: Dimension of the output embedding
        """
        super(SequenceEmbedder, self).__init__()
        
        # Build encoder layers
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Conv1d(prev_dim, hidden_dim, kernel_size=3, padding=1))
            layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.MaxPool1d(kernel_size=2, stride=2))
            prev_dim = hidden_dim
        
        self.encoder = nn.Sequential(*layers)
        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Linear(prev_dim, embedding_dim)
        
    def forward(self, x):
        """Forward pass through the network.
        
        Args:
            x: Input tensor of shape (batch_size, input_dim, sequence_length)
            
        Returns:
            Embedding tensor of shape (batch_size, embedding_dim)
        """
        x = self.encoder(x)
        x = self.global_pool(x).squeeze(-1)
        x = self.fc(x)
        return x


class SequenceDataset(Dataset):
    """Dataset for handling DNA sequences."""
    
    def __init__(self, sequences, labels=None, max_length=1000):
        """Initialize the dataset.
        
        Args:
            sequences: List of DNA sequences
            labels: Optional list of labels for supervised learning
            max_length: Maximum sequence length (sequences will be padded/truncated)
        """
        self.sequences = sequences
        self.labels = labels
        self.max_length = max_length
        
    def __len__(self):
        return len(self.sequences)
    
    def __getitem__(self, idx):
        # Encode sequence as one-hot
        seq = self.sequences[idx]
        encoded_seq = encode_sequences([seq], self.max_length)[0]
        
        if self.labels is not None:
            return encoded_seq, self.labels[idx]
        return encoded_seq


class DeepCluster:
    """Deep clustering model for sequence classification."""
    
    def __init__(self, embedding_dim=128, use_gpu=False):
        """Initialize the deep clustering model.
        
        Args:
            embedding_dim: Dimension of sequence embeddings
            use_gpu: Whether to use GPU acceleration
        """
        self.embedding_dim = embedding_dim
        self.device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
        
        # Initialize embedder
        self.embedder = SequenceEmbedder(embedding_dim=embedding_dim)
        self.embedder.to(self.device)
        
        # Initialize clustering algorithm
        self.clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2, cluster_selection_epsilon=0.5)
        
        # Initialize dimensionality reduction for visualization
        self.umap = UMAP(n_components=2, metric='cosine')
        
    def train_embedder(self, dataloader, epochs=10, lr=0.001):
        """Train the sequence embedder using contrastive learning.
        
        Args:
            dataloader: DataLoader containing sequences
            epochs: Number of training epochs
            lr: Learning rate
        """
        logger.info(f"Training sequence embedder on {self.device}")
        
        # Define loss function and optimizer
        criterion = nn.TripletMarginLoss(margin=1.0)
        optimizer = optim.Adam(self.embedder.parameters(), lr=lr)
        
        self.embedder.train()
        for epoch in range(epochs):
            total_loss = 0
            for batch in dataloader:
                # Generate triplets (anchor, positive, negative)
                # In a real implementation, this would be based on sequence similarity
                # For now, we'll use a simplified approach
                anchors = batch.to(self.device)
                batch_size = anchors.size(0)
                
                # Forward pass
                embeddings = self.embedder(anchors)
                
                # Create triplets
                # This is a simplified implementation - in practice, you'd use more
                # sophisticated triplet mining strategies
                anchor_idx = torch.arange(batch_size)
                positive_idx = (anchor_idx + 1) % batch_size
                negative_idx = (anchor_idx + batch_size // 2) % batch_size
                
                anchor_emb = embeddings[anchor_idx]
                positive_emb = embeddings[positive_idx]
                negative_emb = embeddings[negative_idx]
                
                # Compute loss
                loss = criterion(anchor_emb, positive_emb, negative_emb)
                
                # Backward pass and optimize
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            avg_loss = total_loss / len(dataloader)
            logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
    
    def generate_embeddings(self, dataloader):
        """Generate embeddings for sequences.
        
        Args:
            dataloader: DataLoader containing sequences
            
        Returns:
            Numpy array of embeddings
        """
        logger.info("Generating sequence embeddings")
        
        self.embedder.eval()
        embeddings = []
        
        with torch.no_grad():
            for batch in dataloader:
                batch = batch.to(self.device)
                batch_embeddings = self.embedder(batch)
                embeddings.append(batch_embeddings.cpu().numpy())
        
        return np.vstack(embeddings)
    
    def cluster_sequences(self, embeddings):
        """Cluster sequences based on their embeddings.
        
        Args:
            embeddings: Numpy array of sequence embeddings
            
        Returns:
            Cluster assignments for each sequence
        """
        logger.info("Clustering sequences")
        
        # Fit clustering algorithm
        cluster_labels = self.clusterer.fit_predict(embeddings)
        
        # Count clusters (excluding noise points labeled as -1)
        n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
        logger.info(f"Found {n_clusters} sequence clusters")
        
        return cluster_labels
    
    def visualize_embeddings(self, embeddings, cluster_labels, output_path):
        """Generate visualization of sequence embeddings.
        
        Args:
            embeddings: Numpy array of sequence embeddings
            cluster_labels: Cluster assignments for each sequence
            output_path: Path to save visualization
        """
        logger.info("Generating embedding visualization")
        
        # Reduce dimensionality for visualization
        reduced_embeddings = self.umap.fit_transform(embeddings)
        
        # Save visualization data
        visualization_data = {
            'embeddings_2d': reduced_embeddings,
            'cluster_labels': cluster_labels
        }
        
        save_results(visualization_data, output_path / 'embedding_visualization.pkl')
        
        # Note: Actual plotting would be done in the visualization module
        # This function just prepares and saves the data


def run_classification(input_data, output_dir, reference_db=None, use_gpu=False, threads=1):
    """Run the sequence classification pipeline.
    
    Args:
        input_data: Path to preprocessed sequences or preprocessed data object
        output_dir: Directory to save results
        reference_db: Optional path to reference database for hybrid classification
        use_gpu: Whether to use GPU acceleration
        threads: Number of CPU threads to use
    
    Returns:
        Path to classification results
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Load sequences
    logger.info("Loading sequences for classification")
    sequences = None
    try:
        # If input_data is a path-like and endswith .pkl, load the preprocessed pickle
        if isinstance(input_data, (str, Path)) and str(input_data).lower().endswith('.pkl'):
            preproc = load_results(input_data)
            if isinstance(preproc, dict) and 'sequences' in preproc:
                sequences = preproc['sequences']
            else:
                raise ValueError("Preprocessed data missing 'sequences' key")
        else:
            # Otherwise, assume FASTQ/FASTA or directory
            sequences = load_sequences(input_data)
    except Exception as e:
        logger.exception(f"Failed to load sequences for classification from {input_data}: {e}")
        raise
    
    # Create dataset and dataloader
    dataset = SequenceDataset(sequences)
    dataloader = DataLoader(
        dataset, 
        batch_size=64, 
        shuffle=True, 
        num_workers=threads if threads < 4 else 4
    )
    
    # Initialize and train deep clustering model
    model = DeepCluster(use_gpu=use_gpu)
    model.train_embedder(dataloader, epochs=5)  # Reduced epochs for demonstration
    
    # Generate embeddings
    embeddings = model.generate_embeddings(dataloader)
    
    # Cluster sequences
    cluster_labels = model.cluster_sequences(embeddings)
    
    # Generate visualization
    model.visualize_embeddings(embeddings, cluster_labels, output_dir)
    
    # Save classification results
    classification_results = {
        'sequences': sequences,
        'embeddings': embeddings,
        'cluster_labels': cluster_labels
    }
    
    results_path = output_dir / 'classification_results.pkl'
    save_results(classification_results, results_path)
    
    logger.info(f"Classification results saved to {results_path}")
    
    return results_path


if __name__ == "__main__":
    # This allows the module to be run as a standalone script for testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Run sequence classification')
    parser.add_argument('--input', '-i', required=True, help='Input sequences')
    parser.add_argument('--output', '-o', required=True, help='Output directory')
    parser.add_argument('--gpu', action='store_true', help='Use GPU acceleration')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run classification
    run_classification(args.input, args.output, use_gpu=args.gpu)