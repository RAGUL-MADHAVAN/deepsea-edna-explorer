
import os
import sys
import logging
import pandas as pd
from pathlib import Path
from Bio.Blast import NCBIWWW, NCBIXML
from Bio import SeqIO

# Fix import path to allow running as script
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from src.utils.external_tools import ExternalTool
except ImportError:
    # Fallback if running from root without src module installed
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.external_tools import ExternalTool

logger = logging.getLogger('DeepSeaEDNA.taxonomy')

def _infer_taxonomic_rank(scientific_name, hit_def):
    """Derive a coarse taxonomic rank based on the BLAST hit description."""
    name = (scientific_name or "").strip()
    parts = [p for p in name.split() if p]
    hit_lower = (hit_def or "").lower()
    if name.endswith("idae") or " family" in hit_lower:
        return "family"
    if len(parts) >= 2:
        return "species"
    if len(parts) == 1:
        return "genus"
    return "unknown"

def _extract_scientific_name(hit_def: str) -> str:
    """
    Best-effort extraction of a binomial scientific name from a BLAST hit definition.
    """
    if not hit_def:
        return "Unclassified"
    tokens = [t.strip(" ,;()") for t in str(hit_def).split() if t.strip(" ,;()")]
    if len(tokens) >= 2:
        return f"{tokens[0]} {tokens[1]}"
    if len(tokens) == 1:
        return tokens[0]
    return "Unclassified"

class TaxonomyClassifier:
    def __init__(self, output_dir, db_path=None, allow_remote=True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.blastn = ExternalTool('blastn', mandatory=False)
        self.db_path = db_path
        self.allow_remote = allow_remote
        
    def _infer_marker_from_defs(self, defs):
        s = " ".join([str(d or "").lower() for d in defs])
        if ("16s" in s) or ("ribosomal rna" in s) or ("rrna" in s):
            return "16S rRNA"
        if ("cytochrome c oxidase subunit i" in s) or ("cox1" in s) or ("coi" in s) or ("coxi" in s):
            return "COI"
        if ("its" in s) or ("internal transcribed spacer" in s):
            return "ITS"
        return "Other"

    def run_remote_blast_top_hits(self, input_fasta, hitlist_size=5):
        """Run remote BLAST and return top hits + marker type."""
        logger.info(f"Running remote BLAST for {input_fasta} (top {hitlist_size} hits)")
        sequences = list(SeqIO.parse(input_fasta, "fasta"))
        if not sequences:
            logger.warning("No sequences found.")
            return pd.DataFrame(), "Unknown"
            
        # Only process the first sequence for single-query mode as requested
        seq_record = sequences[0]
        # Check if we have multiple sequences, if so, we should warn or handle them
        if len(sequences) > 1:
            logger.info(f"Multiple sequences found ({len(sequences)}). Processing ALL of them.")
        
        all_hits = []
        all_markers = []

        for seq_record in sequences:
            logger.info(f"Query: {seq_record.id}")
            try:
                result_handle = NCBIWWW.qblast("blastn", "nt", seq_record.seq, hitlist_size=hitlist_size)
                blast_record = NCBIXML.read(result_handle)
                
                # Check for hits
                if not blast_record.alignments:
                    logger.info(f"No hits for {seq_record.id}")
                    continue

                hits = []
                hit_defs = []
                
                for alignment in blast_record.alignments:
                    hsp = alignment.hsps[0]
                    scientific_name = _extract_scientific_name(alignment.hit_def)
                    identity_percent = (hsp.identities / hsp.align_length) * 100
                    query_len = len(seq_record.seq)
                    query_coverage = (hsp.align_length / query_len) * 100 if query_len > 0 else 0.0
                    
                    hits.append({
                        'query_id': seq_record.id,
                        'scientific_name': scientific_name,
                        'hit_def': alignment.hit_def,
                        'e_value': hsp.expect,
                        'identity_percent': identity_percent,
                        'query_coverage': query_coverage,
                        'accession': alignment.accession
                    })
                    hit_defs.append(alignment.hit_def)
                    
                marker_type = self._infer_marker_from_defs(hit_defs)
                all_markers.append(marker_type)
                all_hits.extend(hits)
                
            except Exception as e:
                logger.error(f"Remote BLAST failed for {seq_record.id}: {e}")

        # Determine overall marker type (majority vote or first)
        final_marker = "Unknown"
        if all_markers:
            from collections import Counter
            final_marker = Counter(all_markers).most_common(1)[0][0]

        return pd.DataFrame(all_hits), final_marker

    def choose_best_match(self, df):
        """Select best match based on identity, coverage, e-value."""
        if df.empty:
            return None
        
        # Sort by Identity DESC, Coverage DESC, E-value ASC
        df = df.sort_values(by=['identity_percent', 'query_coverage', 'e_value'], 
                          ascending=[False, False, True])
        best = df.iloc[0].to_dict()
        
        # Apply strict filtering
        # If identity < 97% or coverage < 80%, do not give species name; return genus/family level only.
        if best['identity_percent'] < 97.0 or best['query_coverage'] < 80.0:
            tokens = best['scientific_name'].split()
            if len(tokens) >= 1:
                best['best_name'] = tokens[0] + " sp." # Genus level
                best['best_rank'] = "genus"
            else:
                best['best_name'] = "Unclassified"
                best['best_rank'] = "unknown"
        else:
            best['best_name'] = best['scientific_name']
            best['best_rank'] = "species"
            
        return best

    def run_blast(self, input_fasta, max_seqs=100):
        """Legacy method for pipeline compatibility."""
        # ... (simplified version of original method for compatibility)
        output_xml = self.output_dir / "blast_results.xml"
        if self.allow_remote:
            logger.info("Running remote NCBI BLAST (legacy mode)")
            sequences = list(SeqIO.parse(input_fasta, "fasta"))[:max_seqs]
            results = []
            for seq_record in sequences:
                try:
                    result_handle = NCBIWWW.qblast("blastn", "nt", seq_record.seq, hitlist_size=1)
                    blast_record = NCBIXML.read(result_handle)
                    if blast_record.alignments:
                        alignment = blast_record.alignments[0]
                        hsp = alignment.hsps[0]
                        results.append({
                            'query_id': seq_record.id,
                            'scientific_name': _extract_scientific_name(alignment.hit_def),
                            'identity_percent': (hsp.identities / hsp.align_length) * 100,
                            'query_coverage': (hsp.align_length / len(seq_record.seq)) * 100
                        })
                except Exception:
                    pass
            df = pd.DataFrame(results)
            df.to_csv(self.output_dir / "taxonomy_assignments.csv", index=False)
            return df
        return pd.DataFrame()

    def _parse_blast_xml(self, xml_file):
        # ... (omitted for brevity, not needed for this task)
        pass

if __name__ == "__main__":
    import argparse
    
    # Configure logging to stdout
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    parser = argparse.ArgumentParser(description="Marker detection and remote BLAST top hits")
    parser.add_argument("--input", "-i", required=True, help="Input FASTA file")
    parser.add_argument("--output", "-o", required=True, help="Output directory")
    
    args = parser.parse_args()
    
    clf = TaxonomyClassifier(args.output, allow_remote=True)
    df, marker = clf.run_remote_blast_top_hits(args.input, hitlist_size=5)
    
    print("\n" + "="*50)
    print(f"MARKER TYPE DETECTED: {marker}")
    print("="*50)
    
    if not df.empty:
        # Group by query_id to show results per sequence
        query_ids = df['query_id'].unique() if 'query_id' in df.columns else [None]
        
        for qid in query_ids:
            if qid:
                print(f"\n--- Results for Query: {qid} ---")
                sub_df = df[df['query_id'] == qid]
            else:
                sub_df = df
                
            print(f"TOP 5 HITS:")
            print(sub_df[['scientific_name', 'identity_percent', 'query_coverage', 'e_value']].head(5).to_string(index=False))
            
            best = clf.choose_best_match(sub_df)
            if best:
                print(f"\nBEST RELIABLE MATCH:")
                print(f"Name: {best['best_name']}")
                print(f"Rank: {best['best_rank']}")
                print(f"Identity: {best['identity_percent']:.2f}%")
                print(f"Coverage: {best['query_coverage']:.2f}%")
                print(f"E-value: {best['e_value']}")
            print("-" * 30)
    else:
        print("\nNo BLAST hits found.")
