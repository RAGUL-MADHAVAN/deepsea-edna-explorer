
import os
import logging
from pathlib import Path
from src.utils.external_tools import ExternalTool

logger = logging.getLogger('DeepSeaEDNA.markers')

class MarkerValidator:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.hmmer = ExternalTool('hmmsearch', mandatory=False)
        
    def validate_markers(self, input_fasta, hmm_model=None):
        """
        Validate sequences against HMM models (e.g. 16S, COI).
        Remove off-target reads.
        """
        if not self.hmmer.is_available() or not hmm_model:
            logger.warning("HMMER not found or model missing. Skipping marker validation.")
            return input_fasta
            
        logger.info(f"Validating markers against {hmm_model}...")
        
        output_tbl = self.output_dir / "hmmer_hits.tbl"
        
        args = [
            '--tblout', str(output_tbl),
            '-E', '1e-5', # E-value threshold
            str(hmm_model),
            str(input_fasta)
        ]
        
        try:
            self.hmmer.run(args)
            
            # Parse hits
            valid_ids = set()
            if output_tbl.exists():
                with open(output_tbl, 'r') as f:
                    for line in f:
                        if line.startswith('#'): continue
                        parts = line.split()
                        if len(parts) > 0:
                            valid_ids.add(parts[0]) # Query ID
            
            # Filter FASTA
            from Bio import SeqIO
            output_clean = self.output_dir / "validated_markers.fasta"
            count = 0
            with open(output_clean, "w") as out:
                for record in SeqIO.parse(input_fasta, "fasta"):
                    if record.id in valid_ids:
                        SeqIO.write(record, out, "fasta")
                        count += 1
                        
            logger.info(f"Marker validation kept {count} sequences.")
            return output_clean
            
        except Exception as e:
            logger.error(f"HMMER validation failed: {e}")
            return input_fasta
