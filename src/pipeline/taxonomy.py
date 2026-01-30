
import os
import logging
import pandas as pd
from pathlib import Path
from Bio.Blast import NCBIWWW, NCBIXML
from src.utils.external_tools import ExternalTool


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
    BLAST hit defs can vary a lot; this aims to return something human-readable
    without depending on taxonomy databases.
    """
    if not hit_def:
        return "Unclassified"
    tokens = [t.strip(" ,;()") for t in str(hit_def).split() if t.strip(" ,;()")]
    if len(tokens) >= 2:
        # Common case: "Genus species ..." or "Genus sp. ..."
        return f"{tokens[0]} {tokens[1]}"
    if len(tokens) == 1:
        return tokens[0]
    return "Unclassified"

logger = logging.getLogger('DeepSeaEDNA.taxonomy')

class TaxonomyClassifier:
    def __init__(self, output_dir, db_path=None, allow_remote=True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.blastn = ExternalTool('blastn', mandatory=False)
        self.db_path = db_path
        # When True, fall back to NCBI remote BLAST if local BLAST+ is not configured.
        self.allow_remote = allow_remote
        
    def run_blast(self, input_fasta, max_seqs=100):
        """
        Run BLASTN against a local database or fallback to NCBI Remote BLAST.
        """
        output_xml = self.output_dir / "blast_results.xml"
        
        # 1. Try Local BLAST (preferred: much faster, no external dependency)
        if self.blastn.is_available() and self.db_path:
            logger.info("Running local BLAST")
            args = [
                '-query', str(input_fasta),
                '-db', self.db_path,
                '-outfmt', '5', # XML output
                '-out', str(output_xml),
                '-max_target_seqs', '1',
                '-num_threads', str(os.cpu_count() or 1)
            ]
            try:
                self.blastn.run(args)
                return self._parse_blast_xml(output_xml)
            except Exception as e:
                logger.error(f"Local BLAST failed: {e}. Trying remote...")
        
        # 2. Fallback to Remote BLAST (NCBI)
        if self.allow_remote:
            logger.info("Running remote NCBI BLAST (qblast)")
            from Bio import SeqIO
            
            # Read sequences (limit to a safe number; remote BLAST is slow)
            sequences = list(SeqIO.parse(input_fasta, "fasta"))
            if len(sequences) > max_seqs:
                logger.warning(f"Too many sequences for remote BLAST ({len(sequences)}). Subsampling first {max_seqs}.")
                sequences = sequences[:max_seqs]
                
            results = []
            for i, seq_record in enumerate(sequences):
                if i % 5 == 0:
                    logger.info(f"Remote BLAST for sequence {i+1}/{len(sequences)}...")
                try:
                    # NOTE: NCBI can rate-limit and qblast can be slow; keep hitlist_size small.
                    result_handle = NCBIWWW.qblast("blastn", "nt", seq_record.seq, hitlist_size=1)
                    blast_record = NCBIXML.read(result_handle)
                    
                    if blast_record.alignments:
                        alignment = blast_record.alignments[0]
                        hsp = alignment.hsps[0]
                        scientific_name = _extract_scientific_name(alignment.hit_def)
                        identity_percent = (hsp.identities / hsp.align_length) * 100
                        query_len = len(seq_record.seq)
                        query_coverage = (hsp.align_length / query_len) * 100 if query_len > 0 else 0.0
                        results.append({
                            'query_id': seq_record.id,
                            'scientific_name': scientific_name,
                            'taxonomic_rank': _infer_taxonomic_rank(scientific_name, alignment.hit_def),
                            'hit_def': alignment.hit_def,
                            'e_value': hsp.expect,
                            'identity_percent': identity_percent,
                            'query_coverage': query_coverage
                        })
                    else:
                        results.append({
                            'query_id': seq_record.id,
                            'scientific_name': 'Unclassified',
                            'taxonomic_rank': 'unknown',
                            'hit_def': 'No match found',
                            'e_value': None,
                            'identity_percent': 0.0,
                            'query_coverage': 0.0
                        })
                except Exception as e:
                    logger.error(f"Remote BLAST failed, falling back to Unclassified ({seq_record.id}): {e}")
                    results.append({
                        'query_id': seq_record.id,
                        'scientific_name': 'Unclassified',
                        'taxonomic_rank': 'unknown',
                        'hit_def': 'Remote BLAST failed or unavailable',
                        'e_value': None,
                        'identity_percent': 0.0,
                        'query_coverage': 0.0
                    })
                    
            df = pd.DataFrame(results)
            df.to_csv(self.output_dir / "taxonomy_assignments.csv", index=False)
            return df

        # 3. Neither local BLAST nor remote allowed: emit explicit Unclassified rows
        logger.warning(
            "Neither local BLAST (blastn) nor remote BLAST are available. "
            "Returning Unclassified for all sequences. Configure BLAST+ or enable allow_remote "
            "for real taxonomy assignments."
        )
        from Bio import SeqIO
        results = []
        for record in SeqIO.parse(input_fasta, "fasta"):
            results.append({
                'query_id': record.id,
                'scientific_name': 'Unclassified',
                'taxonomic_rank': 'unknown',
                'hit_def': 'No BLAST available',
                'e_value': None,
                'identity_percent': 0.0,
                'query_coverage': 0.0
            })
        df = pd.DataFrame(results)
        df.to_csv(self.output_dir / "taxonomy_assignments.csv", index=False)
        return df

    def _parse_blast_xml(self, xml_file):
        """Parse BLAST XML output."""
        results = []
        with open(xml_file) as result_handle:
            blast_records = NCBIXML.parse(result_handle)
            for record in blast_records:
                if record.alignments:
                    alignment = record.alignments[0]
                    hsp = alignment.hsps[0]
                    scientific_name = _extract_scientific_name(alignment.hit_def)
                    identity_percent = (hsp.identities / hsp.align_length) * 100
                    try:
                        qlen = int(record.query_length)
                    except Exception:
                        qlen = 0
                    query_coverage = (hsp.align_length / qlen) * 100 if qlen > 0 else 0.0
                    results.append({
                        'query_id': record.query,
                        'scientific_name': scientific_name,
                        'taxonomic_rank': _infer_taxonomic_rank(scientific_name, alignment.hit_def),
                        'hit_def': alignment.hit_def,
                        'e_value': hsp.expect,
                        'identity_percent': identity_percent,
                        'query_coverage': query_coverage
                    })
                else:
                    results.append({
                        'query_id': record.query,
                        'scientific_name': 'Unclassified',
                        'taxonomic_rank': 'unknown',
                        'hit_def': 'No match found',
                        'e_value': None,
                        'identity_percent': 0.0,
                        'query_coverage': 0.0
                    })
        
        df = pd.DataFrame(results)
        df.to_csv(self.output_dir / "taxonomy_assignments.csv", index=False)
        return df
