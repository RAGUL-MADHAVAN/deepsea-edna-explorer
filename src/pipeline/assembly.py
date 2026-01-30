
import os
import logging
from pathlib import Path
from ..utils.external_tools import ExternalTool

logger = logging.getLogger('DeepSeaEDNA.assembly')

class GenomeAssembler:
    """
    Wrapper for genome assembly tools (MEGAHIT, metaSPAdes).
    """
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.megahit = ExternalTool("megahit", mandatory=False)
        self.metaspades = ExternalTool("metaspades.py", mandatory=False)
        self.cdhit = ExternalTool("cd-hit-est", mandatory=False)

    def run_assembly(self, input_reads_1, input_reads_2=None, assembler="megahit"):
        """
        Run assembly on input reads.
        
        Args:
            input_reads_1 (str): Path to forward reads (or single-end reads).
            input_reads_2 (str): Path to reverse reads (optional).
            assembler (str): Preferred assembler ('megahit' or 'metaspades').
            
        Returns:
            Path: Path to the assembled contigs FASTA file.
        """
        out_subdir = self.output_dir / "assembly"
        if out_subdir.exists():
            # Clean up previous run if needed, or handle overwrite
            pass
        
        contigs_file = None
        
        if assembler == "megahit" and self.megahit.is_available():
            contigs_file = self._run_megahit(input_reads_1, input_reads_2, out_subdir)
        elif assembler == "metaspades" and self.metaspades.is_available():
            contigs_file = self._run_metaspades(input_reads_1, input_reads_2, out_subdir)
        elif self.megahit.is_available():
            logger.info("Preferred assembler not found, falling back to MEGAHIT.")
            contigs_file = self._run_megahit(input_reads_1, input_reads_2, out_subdir)
        elif self.metaspades.is_available():
            logger.info("Preferred assembler not found, falling back to metaSPAdes.")
            contigs_file = self._run_metaspades(input_reads_1, input_reads_2, out_subdir)
        else:
            logger.warning("No assembler found (MEGAHIT or metaSPAdes). Skipping assembly step.")
            return None
            
        # Post-process with CD-HIT if available to remove redundancy
        if contigs_file and self.cdhit.is_available():
            contigs_file = self._run_cdhit(contigs_file)
            
        return contigs_file

    def _run_megahit(self, r1, r2, out_dir):
        logger.info("Running MEGAHIT assembly...")
        # MEGAHIT requires output directory to NOT exist
        import shutil
        if out_dir.exists():
            shutil.rmtree(out_dir)
            
        args = ["-o", str(out_dir)]
        if r2:
            args.extend(["-1", str(r1), "-2", str(r2)])
        else:
            args.extend(["-r", str(r1)])
            
        # Add memory/cpu limits if needed
        # args.extend(["--min-count", "2"])
        
        self.megahit.run(args)
        
        final_contigs = out_dir / "final.contigs.fa"
        if final_contigs.exists():
            return final_contigs
        else:
            raise RuntimeError("MEGAHIT finished but final.contigs.fa not found.")

    def _run_metaspades(self, r1, r2, out_dir):
        logger.info("Running metaSPAdes assembly...")
        args = ["-o", str(out_dir)]
        
        if r2:
            args.extend(["-1", str(r1), "-2", str(r2)])
        else:
            args.extend(["-s", str(r1)])
            
        self.metaspades.run(args)
        
        final_contigs = out_dir / "contigs.fasta"
        if final_contigs.exists():
            return final_contigs
        else:
            raise RuntimeError("metaSPAdes finished but contigs.fasta not found.")

    def _run_cdhit(self, input_fasta):
        logger.info("Running CD-HIT-EST to cluster contigs...")
        output_fasta = input_fasta.parent / "contigs.dedup.fasta"
        
        # -i input, -o output, -c sequence identity threshold (0.95), -n word_length, -M memory
        args = [
            "-i", str(input_fasta),
            "-o", str(output_fasta),
            "-c", "0.95",
            "-n", "10",
            "-M", "16000" # 16GB limit
        ]
        
        self.cdhit.run(args)
        return output_fasta
