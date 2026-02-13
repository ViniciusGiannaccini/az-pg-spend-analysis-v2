
import logging
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import json
import base64
import io
import time

# Import your existing classifiers
from src.ml_classifier import load_model_for_sector, predict_batch
from src.hybrid_classifier import classify_hybrid
from src.llm_classifier import classify_items_with_llm
from src.taxonomy_mapper import apply_custom_hierarchy, resolve_unmatched_with_llm

def process_dataframe_chunk(
    df_chunk: pd.DataFrame,
    sector: str,
    desc_column: str,
    hierarchy: Optional[Dict] = None,
    custom_hierarchy: Optional[Dict] = None,
    client_context: str = "",
    use_llm: bool = True
) -> List[Dict]:
    """
    Process a chunk of dataframe rows using the hybrid classification pipeline.
    This function is decoupled from Azure Functions HTTP context.
    """
    
    results = []
    
    # 1. Load Models for Sector
    try:
        vectorizer, classifier, label_encoder, patterns_by_n4, terms_by_n4, taxonomy_by_n4, loaded_hierarchy = load_model_for_sector(sector)
        # Use provided hierarchy if available, otherwise use loaded
        effective_hierarchy = hierarchy or custom_hierarchy or loaded_hierarchy
    except Exception as e:
        logging.error(f"Failed to load models for sector {sector}: {e}")
        # Return error results for this chunk
        return [{"status": "Erro", "LLM_Explanation": f"Model load error: {str(e)}"} for _ in range(len(df_chunk))]

    # 2. Iterate and Classify (First Pass - Hybrid)
    # Using the same logic as ProcessTaxonomy
    total_items = len(df_chunk)
    
    # Pre-calculate normalized descriptions if not present
    if "_desc_norm" not in df_chunk.columns:
        from src.preprocessing import normalize_text
        df_chunk["_desc_norm"] = df_chunk[desc_column].apply(normalize_text)

    # First pass: Local / ML classification
    # We disable LLM fallback here to batch it later
    chunk_results = []
    for idx, row in df_chunk.iterrows():
        desc_orig = str(row[desc_column])
        desc_norm = str(row["_desc_norm"])
        
        result = classify_hybrid(
            description=desc_orig,
            sector=sector,
            dict_patterns=patterns_by_n4,
            dict_terms=terms_by_n4,
            dict_taxonomy=taxonomy_by_n4,
            desc_norm=desc_norm,
            vectorizer=vectorizer,
            classifier=classifier,
            label_encoder=label_encoder,
            hierarchy=effective_hierarchy,
            use_llm_fallback=False, 
            client_context=client_context
        ).to_dict()
        
        # Keep track of original description for LLM pass
        result["_desc_original"] = desc_orig
        chunk_results.append(result)

    # 3. Second Pass: Batch LLM for "Nenhum"
    if use_llm:
        unclassified_indices = [i for i, res in enumerate(chunk_results) if res['status'] == 'Nenhum']
        
        if unclassified_indices:
            logging.info(f"[Chunk] Sending {len(unclassified_indices)} items to LLM...")
            unclassified_descs = [chunk_results[i]["_desc_original"] for i in unclassified_indices]
            
            try:
                llm_batch_results = classify_items_with_llm(
                    unclassified_descs,
                    sector=sector,
                    client_context=client_context,
                    custom_hierarchy=effective_hierarchy
                )
                
                # Merge results
                for i, res in enumerate(llm_batch_results):
                    if res.get("N1"):
                        target_idx = unclassified_indices[i]
                        chunk_results[target_idx].update({
                            "N1": res.get("N1", ""),
                            "N2": res.get("N2", ""),
                            "N3": res.get("N3", ""),
                            "N4": res.get("N4", ""),
                            "status": "Único",
                            "ml_confidence": res.get("confidence", 0.0),
                            "classification_source": "LLM (Batch)"
                        })
            except Exception as e:
                logging.error(f"[Chunk] LLM batch failed: {e}")

        # 4. Third Pass: Semantic Mapping (Standard -> Custom)
        if custom_hierarchy and use_llm:
            # Collect unique N4s from results that are "Único" but not in custom hierarchy
            standard_n4s = set()
            for res in chunk_results:
                if res['status'] == 'Único' and res.get('N4'):
                    n4_key = res['N4'].lower().strip()
                    if n4_key not in custom_hierarchy:
                        standard_n4s.add(res['N4'])
            
            if standard_n4s:
                logging.info(f"[Chunk] Mapping {len(standard_n4s)} standard terms to custom hierarchy...")
                semantic_map = resolve_unmatched_with_llm(list(standard_n4s), custom_hierarchy)
                
                # Re-apply hierarchy with map
                for res in chunk_results:
                    top_candidates = []
                    if res.get('N4'):
                        top_candidates.append({'N4': res['N4']})
                    if res.get('ambiguous_options'):
                        for opt in res['ambiguous_options']:
                            top_candidates.append({'N4': opt})
                            
                    custom_res, matched_n4 = apply_custom_hierarchy(
                        top_candidates, 
                        custom_hierarchy, 
                        semantic_map=semantic_map
                    )
                    
                    if custom_res:
                        res.update({
                            "N1": custom_res.get('N1', ''),
                            "N2": custom_res.get('N2', ''),
                            "N3": custom_res.get('N3', ''),
                            "N4": custom_res.get('N4', ''),
                            "status": "Único",
                            "classification_source": f"Custom (via {res.get('classification_source', '')})"
                        })
                    else:
                        # Fallback to Nenhum if strict mapping
                        if res['status'] == 'Único':
                            orig_n4 = res.get('N4', '')
                            res.update({
                                "N1": "", "N2": "", "N3": "", "N4": "",
                                "status": "Nenhum",
                                "matched_terms": [f'Standard: {orig_n4}'] if orig_n4 else []
                            })

    # Cleanup temporary fields
    for res in chunk_results:
        res.pop("_desc_original", None)

    return chunk_results
