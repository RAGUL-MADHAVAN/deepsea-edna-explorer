
import os
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from Bio import SeqIO

# Pipeline Modules
from src.pipeline.qc import QualityControl
from src.pipeline.decontamination import Decontamination
from src.pipeline.denoising import Denoising
from src.pipeline.marker_validation import MarkerValidator
from src.pipeline.clustering import ClusterAnalysis
from src.pipeline.taxonomy import TaxonomyClassifier
from src.pipeline.assembly import GenomeAssembler
from src.pipeline.phylogeny import PhylogeneticPlacer
from src.pipeline.functional import FunctionalAnnotator
from src.pipeline.abundance import AbundanceEstimator
from src.pipeline.integration import EvidenceIntegrator
from src.utils.visualization import plot_sequence_clusters

logger = logging.getLogger('DeepSeaEDNA.manager')

class PipelineManager:
    def __init__(self, output_dir, use_gpu=False, taxonomy_db_path=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Modules
        self.qc = QualityControl(self.output_dir / "qc")
        self.decontamination = Decontamination(self.output_dir / "qc", reference_db="host_genome") # Placeholder DB
        self.denoising = Denoising(self.output_dir / "denoising")
        self.marker_validator = MarkerValidator(self.output_dir / "markers")
        self.assembly = GenomeAssembler(self.output_dir / "assembly")
        self.clustering = ClusterAnalysis(self.output_dir / "clustering", use_gpu=use_gpu)
        self.taxonomy = TaxonomyClassifier(self.output_dir / "taxonomy", db_path=taxonomy_db_path)
        self.phylogeny = PhylogeneticPlacer(self.output_dir / "phylogeny")
        self.functional = FunctionalAnnotator(self.output_dir / "functional")
        self.abundance = AbundanceEstimator(self.output_dir / "abundance")
        self.integrator = EvidenceIntegrator(self.output_dir / "results")
        
    def run(self, input_file, data_type="amplicon"):
        logger.info(f"Starting pipeline for {input_file} (Type: {data_type})")
        
        # --- Step 1: Pre-processing (Common) ---
        logger.info("--- Step 1: Quality Control ---")
        clean_reads, qc_report = self.qc.run_fastp(input_file)
        
        target_fasta = None
        reads_for_abundance = clean_reads
        
        # --- Step 2: Path-Specific Processing ---
        if data_type == "shotgun":
            logger.info("--- Step 2: Shotgun Processing (Decontamination & Assembly) ---")
            # 2.1 Decontamination
            clean_reads = self.decontamination.run_decontamination(clean_reads)
            reads_for_abundance = clean_reads
            
            # 2.2 Assembly
            contigs = self.assembly.run_assembly(clean_reads)
            
            if contigs and os.path.getsize(contigs) > 0:
                logger.info(f"Assembly successful. Using contigs: {contigs}")
                target_fasta = contigs
                
                # 2.3 Functional Annotation
                logger.info("--- Step 2b: Functional Annotation ---")
                self.functional.run_prokka(target_fasta)
            else:
                logger.warning("Assembly failed or yielded no contigs. Fallback to raw reads (subsampled).")
                # Fallback: Convert FASTQ to FASTA
                target_fasta = self.output_dir / "qc" / "clean_reads.fasta"
                SeqIO.convert(clean_reads, "fastq" if str(clean_reads).endswith("q") else "fasta", target_fasta, "fasta")
                
        else: # Amplicon
            logger.info("--- Step 2: Amplicon Processing (Denoising & Validation) ---")
            # 2.1 Convert to FASTA if needed
            if str(clean_reads).endswith("q"):
                input_fasta = self.output_dir / "qc" / "input.fasta"
                SeqIO.convert(clean_reads, "fastq", input_fasta, "fasta")
            else:
                input_fasta = clean_reads
                
            # 2.2 Denoising (ASV Generation)
            asvs = self.denoising.run_denoising(input_fasta)
            
            # 2.3 Marker Validation
            target_fasta = self.marker_validator.validate_markers(asvs)
            
        # --- Step 3: Abundance Estimation ---
        logger.info("--- Step 3: Abundance Estimation ---")
        abundance_df = self.abundance.estimate_abundance(reads_for_abundance, target_fasta)
        
        # Load Sequences for AI Analysis
        sequences = []
        ids = []
        for record in SeqIO.parse(target_fasta, "fasta"):
            sequences.append(str(record.seq).upper())
            ids.append(record.id)
            
        if not sequences:
            raise ValueError("No valid sequences remaining after processing.")
            
        logger.info(f"Proceeding to AI analysis with {len(sequences)} sequences.")
        
        # --- Step 4: AI Clustering & Novelty ---
        logger.info("--- Step 4: AI Clustering & Novelty Discovery ---")
        clustering_df, cluster_stats = self.clustering.run_clustering(sequences, ids)
        
        # Generate Visualization
        try:
            vis_data = {
                "embeddings_2d": clustering_df[["x", "y"]].to_numpy(),
                "cluster_labels": clustering_df["cluster"].to_numpy()
            }
            results_dir = self.output_dir / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            plot_sequence_clusters(vis_data, results_dir)
        except Exception as e:
            logger.warning(f"Visualization generation failed: {e}")

        # --- Step 5: Taxonomy & Phylogeny ---
        logger.info("--- Step 5: Taxonomy & Phylogeny ---")
        
        # Determine if we should BLAST each sequence individually or use representatives
        n_sequences = len(clustering_df)
        n_clusters = clustering_df['cluster'].nunique()
        
        # Strategy: If few sequences (< 10) OR if sequences are already in different clusters,
        # BLAST each sequence individually to get accurate taxonomy per sequence.
        # Otherwise, use representative-based approach for efficiency.
        use_individual_blast = (n_sequences < 10) or (n_clusters == n_sequences)
        
        if use_individual_blast:
            logger.info(f"BLASTing each sequence individually ({n_sequences} sequences) for accurate per-sequence taxonomy.")
            # BLAST all sequences directly
            taxonomy_df = self.taxonomy.run_blast(target_fasta, max_seqs=min(50, n_sequences))
            
            # Map taxonomy directly by sequence_id (no cluster propagation needed)
            taxonomy_map = {}
            if not taxonomy_df.empty:
                for _, row in taxonomy_df.iterrows():
                    identity_percent = row.get('identity_percent', 0.0) or row.get('identity', 0.0)
                    taxonomy_map[row['query_id']] = {
                        'scientific_name': row['scientific_name'],
                        'confidence': float(identity_percent),
                        'hit_def': row.get('hit_def', ''),
                        'e_value': row.get('e_value', None),
                        'identity_percent': float(identity_percent),
                    }
            
            # Apply taxonomy directly to each sequence
            final_results = clustering_df.copy()
            final_results['scientific_name'] = final_results['sequence_id'].map(lambda sid: taxonomy_map.get(sid, {}).get('scientific_name', 'Unclassified'))
            final_results['confidence'] = final_results['sequence_id'].map(lambda sid: taxonomy_map.get(sid, {}).get('confidence', 0.0))
            final_results['hit_def'] = final_results['sequence_id'].map(lambda sid: taxonomy_map.get(sid, {}).get('hit_def', ''))
            final_results['e_value'] = final_results['sequence_id'].map(lambda sid: taxonomy_map.get(sid, {}).get('e_value', None))
            final_results['identity_percent'] = final_results['sequence_id'].map(lambda sid: taxonomy_map.get(sid, {}).get('identity_percent', 0.0))
        else:
            # Original representative-based approach (for large datasets)
            logger.info(f"Using representative-based BLAST ({n_clusters} clusters from {n_sequences} sequences) for efficiency.")
            # Select Representatives for Taxonomy
            rep_ids = clustering_df.groupby('cluster')['sequence_id'].first().tolist()
            
            # Create Reps FASTA
            reps_fasta = self.output_dir / "taxonomy" / "representatives.fasta"
            with open(reps_fasta, "w") as out:
                for record in SeqIO.parse(target_fasta, "fasta"):
                    if record.id in rep_ids:
                        SeqIO.write(record, out, "fasta")
                        
            # BLAST
            # Keep remote BLAST bounded; representative sequences are already 1/cluster,
            # but large runs can still be slow.
            taxonomy_df = self.taxonomy.run_blast(reps_fasta, max_seqs=25)
            
            # Phylogeny (Optional refinement)
            # self.phylogeny.place_sequences(reps_fasta) # Requires ref tree, skipping for now to ensure run success
            
            # Merge Clustering + Taxonomy
            # Left join clustering with taxonomy on sequence_id (propagating rep taxonomy to cluster)
            
            # 1. Map Rep Taxonomy to Cluster
            cluster_tax_map = {}
            if not taxonomy_df.empty:
                for _, row in taxonomy_df.iterrows():
                    # Find which cluster this rep belongs to
                    cluster = clustering_df[clustering_df['sequence_id'] == row['query_id']]['cluster'].values
                    if len(cluster) > 0:
                        cluster_id = cluster[0]
                        identity_percent = row.get('identity_percent', None)
                        if identity_percent is None:
                            # Backward-compat / alternative naming
                            identity_percent = row.get('identity', 0.0)
                        cluster_tax_map[cluster_id] = {
                            'scientific_name': row['scientific_name'],
                            'confidence': float(identity_percent),  # already percent in taxonomy module
                            'hit_def': row.get('hit_def', ''),
                            'e_value': row.get('e_value', None),
                            'identity_percent': float(identity_percent),
                        }
                        
            # 2. Apply to all sequences
            final_results = clustering_df.copy()
            final_results['scientific_name'] = final_results['cluster'].map(lambda c: cluster_tax_map.get(c, {}).get('scientific_name', 'Unclassified'))
            final_results['confidence'] = final_results['cluster'].map(lambda c: cluster_tax_map.get(c, {}).get('confidence', 0.0))
            final_results['hit_def'] = final_results['cluster'].map(lambda c: cluster_tax_map.get(c, {}).get('hit_def', ''))
            final_results['e_value'] = final_results['cluster'].map(lambda c: cluster_tax_map.get(c, {}).get('e_value', None))
            final_results['identity_percent'] = final_results['cluster'].map(lambda c: cluster_tax_map.get(c, {}).get('identity_percent', 0.0))
        
        # --- Step 6: Final Integration ---
        logger.info("--- Step 6: Final Integration ---")
        
        # 3. Merge Abundance
        if not abundance_df.empty:
            final_results = final_results.merge(abundance_df[['sequence_id', 'count', 'relative_abundance']], on='sequence_id', how='left')
            final_results['count'] = final_results['count'].fillna(0)
            final_results['relative_abundance'] = final_results['relative_abundance'].fillna(0)
            
        # 4. Determine Status
        def determine_status(row):
            if row['scientific_name'] == 'Unclassified':
                if row['novelty_score'] > 0.8: return "High-Novelty Candidate"
                if row['novelty_score'] > 0.5: return "Potential Novel Species"
                return "Unknown"
            else:
                if row['confidence'] < 90: return "Variant / Strain"
                return "Known Species"
                
        final_results['status'] = final_results.apply(determine_status, axis=1)
        
        # Save Final Results
        final_csv = self.output_dir / "results" / "final_results.csv"
        final_results.to_csv(final_csv, index=False)

        # --- Step 7: Biodiversity metrics & abundance by taxonomy ---
        try:
            # Writes abundance_species.csv, abundance_genus.csv, ... and diversity_metrics.csv
            self.abundance.write_taxonomy_abundance_and_diversity(final_results)
        except Exception as e:
            logger.warning(f"Taxonomy abundance/diversity export failed: {e}")
        
        logger.info(f"Pipeline completed successfully. Results at {final_csv}")
        return final_csv, clustering_df, cluster_stats
