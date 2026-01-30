
import os
import logging
from pathlib import Path
from src.utils.external_tools import ExternalTool

logger = logging.getLogger('DeepSeaEDNA.decontamination')

class Decontamination:
    def __init__(self, output_dir, reference_db=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.bowtie2 = ExternalTool('bowtie2', mandatory=False)
        self.reference_db = reference_db
        
    def run_decontamination(self, input_fastq):
        """
        Remove host/contaminant reads by mapping against a reference database.
        Uses Bowtie2 if available.
        """
        if not self.bowtie2.is_available() or not self.reference_db:
            logger.warning("Bowtie2 not found or reference DB not provided. Skipping decontamination.")
            return input_fastq
            
        logger.info(f"Running decontamination against {self.reference_db}...")
        
        output_clean = self.output_dir / "clean_unmapped.fastq"
        output_sam = self.output_dir / "mapped_contaminants.sam"
        
        # Bowtie2 command to output UNMAPPED reads (which are the good ones) to output_clean
        # --un <path> writes unaligned reads to <path>
        args = [
            '-x', self.reference_db,
            '-U', str(input_fastq),
            '--un', str(output_clean),
            '-S', str(output_sam),
            '--threads', str(os.cpu_count() or 1),
            '--very-sensitive-local'
        ]
        
        try:
            self.bowtie2.run(args)
            if output_clean.exists():
                logger.info(f"Decontamination complete. Clean reads: {output_clean}")
                return output_clean
            else:
                logger.warning("Bowtie2 ran but output file missing. Returning original.")
                return input_fastq
        except Exception as e:
            logger.error(f"Decontamination failed: {e}")
            return input_fastq
