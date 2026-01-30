
import os
import logging
from pathlib import Path
from collections import Counter
from Bio import SeqIO
from src.utils.external_tools import ExternalTool

logger = logging.getLogger('DeepSeaEDNA.denoising')

class Denoising:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.vsearch = ExternalTool('vsearch', mandatory=False)
        
    def run_denoising(self, input_fasta):
        """
        Run denoising/ASV generation.
        Prefers VSEARCH for rigorous UNOISE3-like denoising.
        Falls back to Python-based strict dereplication (Exact ASVs).
        """
        
        # 1. VSEARCH Path
        if self.vsearch.is_available():
            logger.info("Running VSEARCH denoising (unoise3)...")
            return self._run_vsearch(input_fasta)
            
        # 2. Python Fallback (Exact ASVs)
        logger.info("VSEARCH not found. Running Python-based Exact ASV generation...")
        return self._run_python_denoising(input_fasta)

    def _run_vsearch(self, input_fasta):
        """Use VSEARCH for dereplication and denoising."""
        derep_fasta = self.output_dir / "derep.fasta"
        centroids_fasta = self.output_dir / "asvs.fasta"
        
        # Step 1: Dereplication
        try:
            self.vsearch.run([
                '--derep_fulllength', str(input_fasta),
                '--output', str(derep_fasta),
                '--sizeout',
                '--minuniquesize', '2'
            ])
            
            # Step 2: Denoising (Cluster Unoise)
            self.vsearch.run([
                '--cluster_unoise', str(derep_fasta),
                '--centroids', str(centroids_fasta),
                '--minsize', '2'
            ])
            
            logger.info(f"VSEARCH ASV generation complete: {centroids_fasta}")
            return centroids_fasta
        except Exception as e:
            logger.error(f"VSEARCH failed: {e}. Falling back to Python.")
            return self._run_python_denoising(input_fasta)

    def _run_python_denoising(self, input_fasta, min_abundance=2):
        """
        Strict Python implementation of Exact ASVs.
        1. Read all sequences.
        2. Count frequencies.
        3. Filter singletons (error reduction).
        4. Return unique sequences as ASVs.
        """
        seqs = []
        for record in SeqIO.parse(input_fasta, "fasta"):
            seqs.append(str(record.seq).upper())
            
        # Adjust min_abundance for small datasets (avoid filtering everything)
        if len(seqs) <= 10:
            logger.info(f"Small dataset detected ({len(seqs)} sequences). Setting min_abundance to 1.")
            min_abundance = 1
            
        counts = Counter(seqs)
        
        # Sort by abundance (descending)
        sorted_asvs = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        
        output_fasta = self.output_dir / "asvs.fasta"
        
        valid_count = 0
        with open(output_fasta, "w") as f:
            for i, (seq, count) in enumerate(sorted_asvs):
                if count >= min_abundance:
                    # Header format: >ASV_1;size=100
                    f.write(f">ASV_{i+1};size={count}\n{seq}\n")
                    valid_count += 1
                    
        # Safety fallback: if we filtered everything, rerun with min_abundance=1
        if valid_count == 0 and min_abundance > 1:
            logger.warning("No ASVs produced; rerunning with min_abundance=1.")
            return self._run_python_denoising(input_fasta, min_abundance=1)

        logger.info(f"Generated {valid_count} Exact ASVs (min_abundance={min_abundance})")
        return output_fasta
