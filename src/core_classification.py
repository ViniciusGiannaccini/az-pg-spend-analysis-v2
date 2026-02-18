
import logging
import unicodedata
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from difflib import get_close_matches
import json
import base64
import io
import time


def _normalize_for_match(text: str) -> str:
    """Remove acentos e normaliza para matching robusto."""
    nfkd = unicodedata.normalize('NFKD', text.lower().strip())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _best_hierarchy_match(n4_text: str, hierarchy_keys: list, norm_keys_map: dict) -> str | None:
    """
    Tenta casar n4_text contra hierarchy_keys usando múltiplas estratégias:
    1. Exact match (case-insensitive)
    2. Exact match normalizado (sem acentos)
    3. Fuzzy match (difflib, cutoff=0.55)
    4. Substring match (n4 contido em key ou vice-versa, min 5 chars)
    """
    key = n4_text.lower().strip()
    norm = _normalize_for_match(n4_text)

    # 1. Exact
    if key in hierarchy_keys:
        return key

    # 2. Normalized exact (sem acentos)
    if norm in norm_keys_map:
        return norm_keys_map[norm]

    # 3. Fuzzy (difflib)
    matches = get_close_matches(key, hierarchy_keys, n=1, cutoff=0.55)
    if matches:
        return matches[0]

    # 4. Substring match (min 5 chars para evitar falsos positivos)
    if len(norm) >= 5:
        for hk, orig_key in norm_keys_map.items():
            if len(hk) >= 5 and (norm in hk or hk in norm):
                return orig_key

    return None

# Import your existing classifiers
from src.ml_classifier import load_model_for_sector, predict_batch
from src.hybrid_classifier import classify_hybrid
from src.llm_classifier import classify_items_with_llm
from src.taxonomy_mapper import apply_custom_hierarchy

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
                # NÃO enviar hierarquia customizada ao LLM — o modelo reasoning
                # fica ~4x mais lento com hierarquia no prompt (276 categorias).
                # O LLM classifica livremente e o Pass 4 mapeia localmente (exact+fuzzy).
                llm_batch_results = classify_items_with_llm(
                    unclassified_descs,
                    sector=sector,
                    client_context=client_context,
                    custom_hierarchy=None
                )
                
                # Merge results (skip LLM failures that return "Não Identificado")
                _UNCLASSIFIED = {"Não Identificado", "Nao Identificado", ""}
                for i, res in enumerate(llm_batch_results):
                    if res.get("N1") and res.get("N1") not in _UNCLASSIFIED:
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

        # 4. Pass 4: Mapeamento local contra hierarquia customizada (sem LLM)
        # O LLM classifica livremente (rápido, sem hierarquia no prompt).
        # Aqui mapeamos os N4s retornados para a hierarquia do cliente via
        # exact match → normalized match → fuzzy match → substring match.
        if custom_hierarchy:
            hierarchy_keys = list(custom_hierarchy.keys())  # lowercase keys
            # Mapa de keys normalizados (sem acentos) → key original
            norm_keys_map = {_normalize_for_match(k): k for k in hierarchy_keys}
            # Cache de matching para não recalcular N4s repetidos
            match_cache = {}

            for res in chunk_results:
                if res['status'] != 'Único' or not res.get('N4'):
                    continue

                n4_val = res['N4']
                cache_key = n4_val.lower().strip()

                if cache_key not in match_cache:
                    match_cache[cache_key] = _best_hierarchy_match(n4_val, hierarchy_keys, norm_keys_map)

                matched_key = match_cache[cache_key]
                if matched_key:
                    h = custom_hierarchy[matched_key]
                    source = "Custom" if matched_key == cache_key else "Custom/fuzzy"
                    res.update({
                        "N1": h.get('N1', ''),
                        "N2": h.get('N2', ''),
                        "N3": h.get('N3', ''),
                        "N4": h.get('N4', n4_val),
                        "classification_source": f"{source} (via {res.get('classification_source', '')})"
                    })
                else:
                    # Sem match — marca como Nenhum
                    res.update({
                        "N1": "", "N2": "", "N3": "", "N4": "",
                        "status": "Nenhum",
                        "matched_terms": [f'Standard: {n4_val}'] if n4_val else []
                    })

            matched = sum(1 for r in chunk_results if r['status'] == 'Único' and r.get('classification_source', '').startswith('Custom'))
            unmatched = sum(1 for r in chunk_results if r.get('matched_terms') and 'Standard:' in str(r.get('matched_terms', '')))
            logging.info(f"[Chunk] Hierarchy mapping: {matched} mapped, {unmatched} unmatched (cache: {len(match_cache)} unique N4s)")

    # Cleanup temporary fields
    for res in chunk_results:
        res.pop("_desc_original", None)

    return chunk_results
