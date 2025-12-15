"""
Custom Taxonomy Mapper for Spend Analysis.

This module handles custom hierarchies provided by clients,
allowing them to override the standard taxonomy with their own.
"""

import pandas as pd
import base64
import io
from typing import Dict, List, Optional, Tuple


def load_custom_hierarchy(base64_content: str) -> Dict[str, Dict]:
    """
    Load custom hierarchy from a base64-encoded Excel/CSV file.
    
    Args:
        base64_content: Base64 encoded file content
        
    Returns:
        Dictionary mapping N4 names to their hierarchy:
        { "N4_name": {"N1": "...", "N2": "...", "N3": "..."} }
    """
    # Decode base64
    file_bytes = base64.b64decode(base64_content)
    
    # Try to read as Excel or CSV
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(f"Could not read file as Excel or CSV: {e}")
    
    # Validate required columns
    required_cols = ['N1', 'N2', 'N3', 'N4']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Build hierarchy mapping
    hierarchy = {}
    for _, row in df.iterrows():
        n4 = str(row['N4']).strip()
        if n4 and n4.lower() != 'nan':
            # Normalize the N4 key for case-insensitive matching
            n4_key = n4.lower()
            hierarchy[n4_key] = {
                'N1': str(row['N1']).strip() if pd.notna(row['N1']) else '',
                'N2': str(row['N2']).strip() if pd.notna(row['N2']) else '',
                'N3': str(row['N3']).strip() if pd.notna(row['N3']) else '',
                'N4': n4  # Keep original case for display
            }
    
    return hierarchy


def apply_custom_hierarchy(
    top_candidates: List[Dict],
    custom_hierarchy: Dict[str, Dict]
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Find the best matching N4 from top candidates in the custom hierarchy.
    
    Args:
        top_candidates: List of ML predictions with N4, confidence, etc.
                       Example: [{"N4": "Alimentos", "confidence": 0.7}, ...]
        custom_hierarchy: Custom hierarchy dict from load_custom_hierarchy()
        
    Returns:
        Tuple of (hierarchy_dict, matched_n4) or (None, None) if no match found
        hierarchy_dict: {"N1": ..., "N2": ..., "N3": ..., "N4": ...}
        matched_n4: The N4 that was matched (original from candidates)
    """
    for candidate in top_candidates:
        n4_predicted = candidate.get('N4', '')
        if not n4_predicted:
            continue
        
        # Try to find in custom hierarchy (case-insensitive)
        n4_key = n4_predicted.lower().strip()
        if n4_key in custom_hierarchy:
            return custom_hierarchy[n4_key], n4_predicted
    
    # No match found
    return None, None


def get_hierarchy_stats(custom_hierarchy: Dict[str, Dict]) -> Dict:
    """
    Get statistics about the custom hierarchy.
    
    Returns:
        Dict with counts of N1, N2, N3, N4
    """
    n1s = set()
    n2s = set()
    n3s = set()
    n4s = set()
    
    for n4_key, hierarchy in custom_hierarchy.items():
        n1s.add(hierarchy.get('N1', ''))
        n2s.add(hierarchy.get('N2', ''))
        n3s.add(hierarchy.get('N3', ''))
        n4s.add(hierarchy.get('N4', ''))
    
    return {
        'n1_count': len(n1s),
        'n2_count': len(n2s),
        'n3_count': len(n3s),
        'n4_count': len(n4s)
    }
