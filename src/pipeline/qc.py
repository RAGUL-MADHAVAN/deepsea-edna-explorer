
import os
import logging
from pathlib import Path
from src.utils.external_tools import ExternalTool

logger = logging.getLogger('DeepSeaEDNA.qc')

class QualityControl:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fastp = ExternalTool('fastp', mandatory=False)
        
    def run_fastp(self, input_file, prefix="sample"):
        """
        Run fastp for quality control.
        """
        if not self.fastp.is_available():
            logger.warning("fastp not found. Skipping QC step and using raw input.")
            return input_file, None

        input_path = Path(input_file)
        clean_fastq = self.output_dir / f"{prefix}_clean.fastq"
        html_report = self.output_dir / f"{prefix}_fastp.html"
        json_report = self.output_dir / f"{prefix}_fastp.json"
        
        args = [
            '-i', str(input_path),
            '-o', str(clean_fastq),
            '-h', str(html_report),
            '-j', str(json_report),
            '--detect_adapter_for_pe'
        ]
        
        try:
            self.fastp.run(args)
            logger.info(f"QC completed. Clean reads: {clean_fastq}")
            return clean_fastq, json_report
        except Exception as e:
            logger.error(f"QC failed: {e}")
            # Fallback to input file if QC fails
            return input_file, None

    def filter_length(self, input_file, min_length=100):
        """
        Simple length filtering using Biopython if fastp is not available or for additional filtering.
        """
        from Bio import SeqIO
        
        output_file = self.output_dir / f"{Path(input_file).stem}_filtered.fasta"
        
        count = 0
        with open(output_file, "w") as out_handle:
            for record in SeqIO.parse(input_file, "fastq" if str(input_file).endswith("q") else "fasta"):
                if len(record.seq) >= min_length:
                    SeqIO.write(record, out_handle, "fasta")
                    count += 1
                    
        logger.info(f"Filtered {count} sequences >= {min_length}bp")
        return output_file
