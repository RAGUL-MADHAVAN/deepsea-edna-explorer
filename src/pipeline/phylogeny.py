
import os
import logging
from pathlib import Path
from ..utils.external_tools import ExternalTool

logger = logging.getLogger('DeepSeaEDNA.phylogeny')

class PhylogeneticPlacer:
    """
    Wrapper for Phylogenetic Placement tools (EPA-ng, GAPPA, MAFFT).
    """
    def __init__(self, output_dir, reference_tree=None, reference_alignment=None, reference_model=None):
        self.output_dir = Path(output_dir)
        self.reference_tree = reference_tree
        self.reference_alignment = reference_alignment
        self.reference_model = reference_model # e.g. GTR+G
        
        # Tools
        self.mafft = ExternalTool("mafft", mandatory=False)
        self.epang = ExternalTool("epa-ng", mandatory=False)
        self.gappa = ExternalTool("gappa", mandatory=False)
        self.hmmalign = ExternalTool("hmmalign", mandatory=False) # Alternative to mafft --add

    def align_to_reference(self, query_fasta):
        """
        Align query sequences to the reference alignment using MAFFT.
        """
        if not self.mafft.is_available():
            logger.warning("MAFFT not found. Skipping alignment.")
            return None
            
        if not self.reference_alignment or not os.path.exists(self.reference_alignment):
            logger.warning("Reference alignment not provided. Skipping placement alignment.")
            return None

        out_aln = self.output_dir / "query_aligned.fasta"
        
        # mafft --add query.fasta reference_aln.fasta > output.fasta
        args = [
            "--add", str(query_fasta),
            "--reorder",
            str(self.reference_alignment)
        ]
        
        # We need to capture stdout for mafft
        logger.info("Running MAFFT alignment...")
        with open(out_aln, "w") as f:
            # We can't use the standard run() helper easily for stdout redirection 
            # unless we modify it, so let's use subprocess directly here or 
            # if run() supports it. 
            # Let's use the tool's executable path.
            import subprocess
            cmd = [self.mafft.executable] + args
            subprocess.run(cmd, stdout=f, check=True)
            
        return out_aln

    def run_placement(self, query_fasta):
        """
        Run EPA-ng to place sequences on the reference tree.
        """
        if not self.epang.is_available():
            logger.warning("EPA-ng not found. Skipping phylogenetic placement.")
            return None

        # 1. Align queries
        aligned_query = self.align_to_reference(query_fasta)
        if not aligned_query:
            return None

        # 2. Run EPA-ng
        # epa-ng --tree ref.tree --ref-msa ref.fasta --query query_aligned.fasta --model GTR+G --out-dir output
        logger.info("Running EPA-ng placement...")
        
        args = [
            "--tree", str(self.reference_tree),
            "--ref-msa", str(self.reference_alignment),
            "--query", str(aligned_query),
            "--out-dir", str(self.output_dir),
            "--redo" # Overwrite
        ]
        
        if self.reference_model:
            args.extend(["--model", self.reference_model])
            
        self.epang.run(args)
        
        jplace_file = self.output_dir / "epa_result.jplace"
        if jplace_file.exists():
            return jplace_file
        else:
            logger.error("EPA-ng finished but jplace file not found.")
            return None
            
    def visualize_placement(self, jplace_file):
        """
        Use GAPPA to generate visualization/analysis of the placement.
        """
        if not self.gappa.is_available():
            return None
            
        logger.info("Running GAPPA analysis...")
        # Example: gappa examine heat-tree --jplace-path result.jplace --out-dir output
        args = [
            "examine", "heat-tree",
            "--jplace-path", str(jplace_file),
            "--out-dir", str(self.output_dir),
            "--allow-file-overwriting"
        ]
        
        self.gappa.run(args)
        
        # Check for expected outputs (e.g., SVG/ITOL files)
        return self.output_dir
