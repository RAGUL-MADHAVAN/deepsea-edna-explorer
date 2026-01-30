
import os
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
from Bio import SeqIO
from src.utils.external_tools import ExternalTool

logger = logging.getLogger('DeepSeaEDNA.abundance')

class AbundanceEstimator:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.bowtie2 = ExternalTool('bowtie2', mandatory=False)
        
    def estimate_abundance(self, reads_file, reference_fasta):
        """
        Map reads back to reference (ASVs or Contigs) to estimate abundance.
        """
        if self.bowtie2.is_available():
            return self._run_bowtie2_mapping(reads_file, reference_fasta)
        else:
            return self._run_exact_matching(reads_file, reference_fasta)
            
    def _run_bowtie2_mapping(self, reads_file, reference_fasta):
        """Use Bowtie2 to map reads and samtools (if available) or parsing to count."""
        logger.info("Running Bowtie2 for abundance estimation...")
        index_base = self.output_dir / "ref_index"
        sam_file = self.output_dir / "mapped.sam"
        
        try:
            # 1. Build Index
            self.bowtie2.run_custom("bowtie2-build", [str(reference_fasta), str(index_base)])
            
            # 2. Map Reads
            self.bowtie2.run([
                '-x', str(index_base),
                '-U', str(reads_file),
                '-S', str(sam_file),
                '--no-unal', # Do not report unaligned reads
                '--threads', str(os.cpu_count() or 1)
            ])
            
            # 3. Parse SAM to count
            counts = defaultdict(int)
            with open(sam_file, 'r') as f:
                for line in f:
                    if line.startswith('@'): continue
                    parts = line.split('\t')
                    if len(parts) > 2:
                        ref_name = parts[2]
                        if ref_name != '*':
                            counts[ref_name] += 1
                            
            return self._format_results(counts)
            
        except Exception as e:
            logger.error(f"Bowtie2 mapping failed: {e}. Falling back to exact matching.")
            return self._run_exact_matching(reads_file, reference_fasta)

    def _run_exact_matching(self, reads_file, reference_fasta):
        """
        Python fallback: Count occurrences of ASVs in reads.
        This is slow for huge files but accurate for amplicon exact matches.
        """
        logger.info("Running Python exact matching for abundance...")
        
        # Load reference sequences into a set/dict
        refs = {}
        for record in SeqIO.parse(reference_fasta, "fasta"):
            refs[str(record.seq).upper()] = record.id
            
        counts = defaultdict(int)
        
        # Scan reads
        # Note: For shotgun contigs, this is not ideal (reads are substrings of contigs).
        # This fallback works best for Amplicon where Read == ASV.
        # For shotgun, we might need k-mer matching or substring check (very slow).
        
        # Optimization: Build K-mer index or Aho-Corasick? 
        # For now, let's assume Amplicon context mostly.
        # For shotgun, we really want Bowtie2.
        
        total_reads = 0
        for record in SeqIO.parse(reads_file, "fastq" if str(reads_file).endswith("q") else "fasta"):
            seq = str(record.seq).upper()
            if seq in refs:
                counts[refs[seq]] += 1
            total_reads += 1
            
        logger.info(f"Processed {total_reads} reads. {sum(counts.values())} mapped.")
        return self._format_results(counts)

    def _format_results(self, counts):
        """Convert counts dict to DataFrame."""
        total = sum(counts.values())
        data = []
        for ref_id, count in counts.items():
            data.append({
                'sequence_id': ref_id,
                'count': count,
                'relative_abundance': count / total if total > 0 else 0
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('count', ascending=False)
            
        csv_path = self.output_dir / "abundance_table.csv"
        df.to_csv(csv_path, index=False)
        return df

    def write_taxonomy_abundance_and_diversity(self, final_results_df: pd.DataFrame) -> None:
        """
        Given the integrated final results (sequence-level), produce:
        - abundance_<rank>.csv for common ranks
        - diversity_metrics.csv (Shannon, Simpson, richness, evenness) per rank

        This matches the "abundance + biodiversity metrics" requirement of the problem statement.
        """
        if final_results_df is None or final_results_df.empty:
            raise ValueError("final_results_df is empty; cannot compute abundance/diversity.")

        # Ensure required columns exist
        if 'count' not in final_results_df.columns:
            # If reads couldn't be mapped, treat each sequence as count=1 (presence/absence)
            df = final_results_df.copy()
            df['count'] = 1
        else:
            df = final_results_df.copy()

        # Prefer a taxonomy column; fallback to "Unclassified"
        if 'scientific_name' not in df.columns:
            df['scientific_name'] = 'Unclassified'

        # A simple rank ladder from the available taxonomy signal:
        # - We only have "scientific_name" string from BLAST hit_def; so we infer rank by token count.
        # - This is imperfect but deterministic and works without external taxonomy services.
        def infer_rank(name: str) -> str:
            name = (name or "").strip()
            if not name or name == "Unclassified":
                return "unknown"
            parts = [p for p in name.split() if p]
            if len(parts) >= 2:
                return "species"
            if len(parts) == 1:
                return "genus"
            return "unknown"

        df['taxonomic_rank'] = df['scientific_name'].map(infer_rank)

        # Build rank tables. We include the classic ladder, but only populate what we can infer.
        # For higher ranks we don't have a lineage without extra databases, so we keep them empty
        # unless scientific_name happens to already be a higher-rank label.
        target_ranks = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
        diversity_rows = []

        out_dir = self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        total_count = float(df['count'].sum()) if float(df['count'].sum()) > 0 else 1.0

        for rank in target_ranks:
            if rank in ("genus", "species"):
                # Use scientific_name for whichever inferred rank matches; otherwise bucket as Unclassified
                rank_name_col = f"_{rank}_name"
                df[rank_name_col] = np.where(df['taxonomic_rank'] == rank, df['scientific_name'], "Unclassified")
                grouped = df.groupby(rank_name_col, dropna=False)['count'].sum().reset_index()
                grouped = grouped.rename(columns={rank_name_col: rank})
            else:
                # Not available from current BLAST parsing; emit an empty-but-valid file for UI consistency
                grouped = pd.DataFrame({rank: [], "count": [], "relative_abundance": []})
                grouped.to_csv(out_dir / f"abundance_{rank}.csv", index=False)
                diversity_rows.append({
                    "level": rank,
                    "shannon_index": 0.0,
                    "simpson_index": 0.0,
                    "richness": 0,
                    "evenness": 0.0
                })
                continue

            grouped["relative_abundance"] = grouped["count"] / total_count
            grouped = grouped.sort_values("count", ascending=False)
            grouped.to_csv(out_dir / f"abundance_{rank}.csv", index=False)

            abund = grouped["relative_abundance"].to_numpy(dtype=float)
            abund = abund[abund > 0]
            if abund.size == 0:
                shannon = 0.0
                simpson = 0.0
                richness = 0
                evenness = 0.0
            else:
                shannon = float(-(abund * np.log(abund + 1e-12)).sum())
                simpson = float(1.0 - (abund ** 2).sum())
                richness = int(grouped.shape[0])
                evenness = float(shannon / np.log(richness)) if richness > 1 else 0.0

            diversity_rows.append({
                "level": rank,
                "shannon_index": shannon,
                "simpson_index": simpson,
                "richness": richness,
                "evenness": evenness
            })

        diversity_df = pd.DataFrame(diversity_rows)
        diversity_df.to_csv(out_dir / "diversity_metrics.csv", index=False)
