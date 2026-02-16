"""
Custom Taxonomy Mapper for Spend Analysis.

This module handles custom hierarchies provided by clients,
allowing them to override the standard taxonomy with their own.
"""

import pandas as pd
import base64
import io
from difflib import get_close_matches
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
        df = pd.read_excel(io.BytesIO(file_bytes), engine='openpyxl')
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(f"Could not read file as Excel or CSV: {e}")
    
    # Normalize column headers (handle casing and whitespace)
    df.columns = [str(col).strip().upper() for col in df.columns]
    
    # Validate required columns
    required_cols = ['N1', 'N2', 'N3', 'N4']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}. Please use 'N1', 'N2', 'N3', 'N4' as headers.")
    
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
    custom_hierarchy: Dict[str, Dict],
    semantic_map: Optional[Dict[str, str]] = None
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
    # First pass: Look for exact matches (case-insensitive) in top candidates
    for candidate in top_candidates:
        n4_predicted = candidate.get('N4', '')
        if not n4_predicted:
            continue
        
        n4_key = n4_predicted.lower().strip()
        if n4_key in custom_hierarchy:
            return custom_hierarchy[n4_key], n4_predicted
    
    # Second pass: Fuzzy matching (only if ML provides a strong lead)
    # We take the top ML candidate and find the most similar string in our custom hierarchy keys
    if top_candidates:
        n4_ml = str(top_candidates[0].get('N4', '')).lower().strip()
        
        # 2a. Check Semantic Map (LLM-based) if provided
        if n4_ml and semantic_map and n4_ml in semantic_map:
            mapped_key = semantic_map[n4_ml]
            if mapped_key in custom_hierarchy:
                return custom_hierarchy[mapped_key], top_candidates[0]['N4']

        # 2b. Fuzzy matching
        try:
            if n4_ml:
                # Find best string match (min score 0.6)
                matches = get_close_matches(n4_ml, custom_hierarchy.keys(), n=1, cutoff=0.6)
                if matches:
                    matched_key = matches[0]
                    return custom_hierarchy[matched_key], top_candidates[0]['N4']
        except Exception:
            pass # Fall back to None if fuzzy matching fails

    # No match found
    return None, None


def resolve_unmatched_with_llm(
    unmatched_n4s: List[str],
    custom_hierarchy: Dict[str, Dict]
) -> Dict[str, str]:
    """
    Use LLM to semantically map unmatched standard N4s to custom hierarchy keys.
    
    Args:
        unmatched_n4s: List of N4s from standard model that didn't match.
        custom_hierarchy: The target hierarchy to map to.
        
    Returns:
        Dictionary mapping Standard N4 -> Custom N4 key (lowercase)
    """
    if not unmatched_n4s:
        return {}
        
    # Lazy import to avoid circular dependency
    from src.llm_classifier import map_categories_with_llm
    
    # Get all target N4 keys
    target_categories = sorted(list(set(h['N4'] for h in custom_hierarchy.values())))
    
    # Call LLM
    mapping = map_categories_with_llm(unmatched_n4s, target_categories)
    
    # Normalize keys and values for lookup
    normalized_map = {}
    for k, v in mapping.items():
        if v and v != "Não Identificado":
            # Map lowercase standard N4 -> lowercase custom N4 key
            normalized_map[k.lower().strip()] = v.lower().strip()
            
    return normalized_map


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
