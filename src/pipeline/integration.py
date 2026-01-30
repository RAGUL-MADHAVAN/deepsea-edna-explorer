
import logging
import pandas as pd
from pathlib import Path

logger = logging.getLogger('DeepSeaEDNA.integration')

class EvidenceIntegrator:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def integrate_results(self, amplicon_df=None, shotgun_df=None):
        """
        Integrate results from Amplicon and Shotgun paths.
        For now, this merges taxonomy tables and highlights shared taxa.
        """
        logger.info("Integrating cross-evidence from available data...")
        
        merged_data = []
        
        # If we only have one source, just return it formatted
        if amplicon_df is None and shotgun_df is None:
            return pd.DataFrame()
            
        if amplicon_df is not None:
            amplicon_df['source'] = 'Amplicon'
            merged_data.append(amplicon_df)
            
        if shotgun_df is not None:
            shotgun_df['source'] = 'Shotgun'
            merged_data.append(shotgun_df)
            
        if not merged_data:
            return pd.DataFrame()
            
        full_df = pd.concat(merged_data, ignore_index=True)
        
        # Calculate prevalence/evidence score
        # Group by Taxonomy (scientific_name)
        if 'scientific_name' in full_df.columns:
            summary = full_df.groupby('scientific_name').agg({
                'source': lambda x: list(set(x)),
                'sequence_id': 'count'
            }).reset_index()
            
            summary['evidence_level'] = summary['source'].apply(
                lambda x: 'Strong (Multi-Source)' if len(x) > 1 else f'Single Source ({x[0]})'
            )
            
            summary.to_csv(self.output_dir / "integrated_evidence.csv", index=False)
            return summary
            
        return full_df
