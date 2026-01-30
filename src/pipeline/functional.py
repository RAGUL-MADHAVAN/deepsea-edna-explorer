
import os
import logging
from pathlib import Path
from ..utils.external_tools import ExternalTool

logger = logging.getLogger('DeepSeaEDNA.functional')

class FunctionalAnnotator:
    """
    Wrapper for functional annotation tools (Prokka).
    """
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.prokka = ExternalTool("prokka", mandatory=False)

    def run_prokka(self, contigs_file, sample_name="sample"):
        """
        Run Prokka on assembled contigs.
        
        Args:
            contigs_file (Path): Path to the contigs FASTA file.
            sample_name (str): Prefix for output files.
            
        Returns:
            Path: Path to the output directory containing annotation results.
        """
        if not self.prokka.is_available():
            logger.warning("Prokka not found. Skipping functional annotation.")
            return None
            
        out_subdir = self.output_dir / "annotation"
        
        # Prokka fails if output dir exists, unless --force is used
        args = [
            "--outdir", str(out_subdir),
            "--prefix", sample_name,
            "--force",
            "--cpus", "0", # Auto detect
            str(contigs_file)
        ]
        
        # Optional: Add kingdom specific flags if known (e.g. --kingdom Bacteria)
        # For eDNA, we might leave it generic or run multiple times? 
        # Prokka is mainly for Bacteria/Archaea/Viruses.
        # For Eukaryotes, we might need other tools, but user specifically asked for Prokka.
        
        logger.info(f"Running Prokka on {contigs_file}...")
        self.prokka.run(args)
        
        # Check for .gff or .tbl output
        gff_file = out_subdir / f"{sample_name}.gff"
        if gff_file.exists():
            return out_subdir
        else:
            logger.error("Prokka finished but GFF file not found.")
            return None
