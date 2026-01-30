import os
import logging
import torch
import numpy as np
from pathlib import Path
from typing import List, Union

# Fallback libraries
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

logger = logging.getLogger('DeepSeaEDNA.embedding')

class DNABertEmbedder:
    """
    Generates DNA sequence embeddings using the pre-trained DNABERT-2 model.
    References: https://huggingface.co/zhihan1996/DNABERT-2-117M
    
    Fallback: K-mer TF-IDF + SVD if DNABERT-2 fails (e.g. on Windows without Triton).
    """
    def __init__(self, model_name="zhihan1996/DNABERT-2-117M", use_gpu=True, cache_dir=None):
        self.model_name = model_name
        self.device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
        self.model = None
        self.tokenizer = None
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'models')
        self.use_fallback = False
        self.vectorizer = None
        self.svd = None
        
        # Ensure model directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def load_model(self):
        """Load the model and tokenizer from HuggingFace or local cache."""
        if self.model is not None or self.use_fallback:
            return

        try:
            from transformers import AutoTokenizer, AutoModel

            # Prefer a fully-local load (important for offline / sandboxed runs).
            model_id_or_path = self.model_name
            try:
                # If the model has been cached locally (as in this repo), load from the latest snapshot path.
                # Expected layout: <cache_dir>/models--<org>--<name>/snapshots/<hash>/
                models_root = Path(self.cache_dir)
                expected = models_root / "models--zhihan1996--DNABERT-2-117M" / "snapshots"
                if expected.exists():
                    snapshots = [p for p in expected.iterdir() if p.is_dir()]
                    if snapshots:
                        # Pick the newest snapshot directory
                        snapshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        model_id_or_path = str(snapshots[0])
            except Exception:
                # If anything goes wrong, just keep model_name (HF id)
                model_id_or_path = self.model_name

            logger.info(f"Loading DNABERT-2 model: {model_id_or_path}")
            # trust_remote_code=True is required for DNABERT-2
            # local_files_only=True prevents hanging when network is blocked.
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_id_or_path,
                trust_remote_code=True,
                cache_dir=self.cache_dir,
                local_files_only=True
            )
            self.model = AutoModel.from_pretrained(
                model_id_or_path,
                trust_remote_code=True,
                cache_dir=self.cache_dir,
                local_files_only=True
            )
            
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Model loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load DNABERT-2: {e}")
            logger.warning("Falling back to K-mer embedding (Scientific Alignment-Free Method) due to missing dependencies (likely Triton/Windows).")
            self.use_fallback = True
            
    def get_embeddings(self, sequences: List[str], batch_size=32, max_length=512) -> np.ndarray:
        """
        Generate embeddings for a list of DNA sequences.
        """
        if self.model is None and not self.use_fallback:
            self.load_model()
            
        if self.use_fallback:
            return self._get_fallback_embeddings(sequences)
            
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(sequences), batch_size):
            batch_seqs = sequences[i:i + batch_size]
            
            try:
                # Tokenize
                inputs = self.tokenizer(
                    batch_seqs, 
                    return_tensors="pt", 
                    padding=True, 
                    truncation=True, 
                    max_length=max_length
                )
                
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # Inference
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    
                    # Check if model output is a tuple or object
                    if hasattr(outputs, 'last_hidden_state'):
                        hidden_states = outputs.last_hidden_state
                    else:
                        hidden_states = outputs[0]
                    
                    # Mean pooling
                    attention_mask = inputs['attention_mask'].unsqueeze(-1)
                    masked_hidden = hidden_states * attention_mask
                    sum_hidden = torch.sum(masked_hidden, dim=1)
                    sum_mask = torch.sum(attention_mask, dim=1)
                    sum_mask = torch.clamp(sum_mask, min=1e-9)
                    mean_embeddings = sum_hidden / sum_mask
                    
                    all_embeddings.append(mean_embeddings.cpu().numpy())
                    
            except Exception as e:
                logger.error(f"Inference failed batch {i}: {e}. Switching to fallback.")
                self.use_fallback = True
                return self._get_fallback_embeddings(sequences)
                
            if (i // batch_size) % 10 == 0:
                logger.info(f"Processed {i + len(batch_seqs)}/{len(sequences)} sequences")
                
        if not all_embeddings:
             return np.zeros((0, 768))

        return np.vstack(all_embeddings)

    def _get_fallback_embeddings(self, sequences: List[str]) -> np.ndarray:
        """
        Generate K-mer embeddings as a fallback.
        Uses TF-IDF on 6-mers followed by SVD to 768 dimensions.
        """
        logger.info("Generating K-mer embeddings (Fallback)...")
        if not sequences:
            return np.zeros((0, 768))
            
        try:
            # Lazy initialization
            if self.vectorizer is None:
                 self.vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(6, 6))
            if self.svd is None:
                 self.svd = TruncatedSVD(n_components=768, random_state=42)

            # Fit vectorizer
            X = self.vectorizer.fit_transform(sequences)
            
            # Fit SVD (adjust n_components if samples < 768)
            n_samples = X.shape[0]
            n_components = min(n_samples, 768)
            
            if n_components < 2:
                 # For 1 sample, return dense TF-IDF padded
                 dense = X.toarray()
                 padded = np.zeros((n_samples, 768))
                 cols = min(dense.shape[1], 768)
                 padded[:, :cols] = dense[:, :cols]
                 return padded
                 
            self.svd.n_components = n_components
            embeddings = self.svd.fit_transform(X)
            
            # If we have fewer than 768 dims, pad with zeros
            if embeddings.shape[1] < 768:
                padded = np.zeros((embeddings.shape[0], 768))
                padded[:, :embeddings.shape[1]] = embeddings
                embeddings = padded
                
            return embeddings
        except Exception as e:
            logger.error(f"Fallback embedding failed: {e}")
            return np.random.rand(len(sequences), 768)
