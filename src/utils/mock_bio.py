#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mock bioinformatics utilities for hackathon demo.

These functions simulate HMM-based marker detection and BLAST similarity search.
In production, these steps would be executed using tools like HMMER/BLAST.
"""

import json
import logging
import random
from pathlib import Path

from src.utils.io import save_results

logger = logging.getLogger('DeepSeaEDNA.utils.mock_bio')


def simulate_hmm_marker_detection(sequences, output_dir):
    """Simulate HMM marker / eukaryote detection for demo."""
    logger.info("Simulating HMM marker detection (demo)")
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    markers = ['18S_rRNA', 'COI', 'ITS']
    detected = []
    for seq in sequences:
        detected.append({
            'sequence_id': f"seq_{random.randint(1000, 9999)}",
            'marker': random.choice(markers),
            'hmm_score': round(random.uniform(25.0, 120.0), 2),
            'eukaryote_prob': round(random.uniform(0.6, 0.99), 3)
        })

    summary = {
        'total_sequences': len(sequences),
        'markers_detected': list({d['marker'] for d in detected}),
        'avg_hmm_score': round(sum(d['hmm_score'] for d in detected) / max(len(detected), 1), 2)
    }

    results = {
        'summary': summary,
        'detections': detected
    }

    save_results(results, output_dir / 'hmm_marker_results.pkl')
    with open(output_dir / 'hmm_marker_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return results


def simulate_blast_similarity(sequences, output_dir):
    """Simulate BLAST similarity search for demo."""
    logger.info("Simulating BLAST similarity search (demo)")
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    taxa = [
        'Bathypelagic Coralline sp.',
        'Abyssal Cnidaria sp.',
        'Deep-sea Polychaete sp.',
        'Hydrothermal Vent Protist sp.',
        'Unknown Eukaryote sp.'
    ]

    hits = []
    for seq in sequences:
        hits.append({
            'sequence_id': f"seq_{random.randint(1000, 9999)}",
            'top_hit': random.choice(taxa),
            'identity': round(random.uniform(75.0, 99.5), 2),
            'evalue': 10 ** (-random.randint(5, 50))
        })

    results = {
        'total_sequences': len(sequences),
        'top_hits': hits
    }

    save_results(results, output_dir / 'blast_results.pkl')
    with open(output_dir / 'blast_summary.json', 'w', encoding='utf-8') as f:
        json.dump({
            'total_sequences': len(sequences),
            'unique_hits': len({h['top_hit'] for h in hits})
        }, f, indent=2)

    return results
