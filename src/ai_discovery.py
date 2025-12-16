"""
AI Discovery Module for Spend Analysis.

This module provides "Zero-Shot" classification and Taxonomy Discovery capabilities
using local embeddings (sentence-transformers) and clustering.

It is designed to run on Azure Functions (CPU) without external API dependencies.
"""

import logging
import os
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Any
from functools import lru_cache

# Lazy import to avoid cold start impact if not used
# from sentence_transformers import SentenceTransformer
# from sklearn.cluster import MiniBatchKMeans
# from sklearn.metrics.pairwise import cosine_similarity

# Constants
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "cache")
MAX_CLUSTER_SAMPLES = 5
DEFAULT_N_CLUSTERS = 30  # Default number of clusters for discovery


class AIModelManager:
    """Singleton-like manager for the heavy embedding model."""
    _instance = None
    _model = None

    @classmethod
    def get_model(cls):
        """Load and return the SentenceTransformer model (cached)."""
        if cls._model is None:
            logging.info(f"Loading embedding model: {MODEL_NAME}...")
            # Ensure cache dir exists
            os.makedirs(CACHE_DIR, exist_ok=True)
            
            from sentence_transformers import SentenceTransformer
            cls._model = SentenceTransformer(MODEL_NAME, cache_folder=CACHE_DIR)
            logging.info("Embedding model loaded successfully.")
        return cls._model


def generate_embeddings(texts: List[str], batch_size: int = 32) -> np.ndarray:
    """
    Generate embeddings for a list of texts using the local model.
    """
    if not texts:
        return np.array([])
    
    model = AIModelManager.get_model()
    
    # Normalize texts (basic cleanup)
    texts = [str(t).strip() for t in texts]
    
    # Generate embeddings
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    return embeddings


def cluster_items(
    items: List[str], 
    n_clusters: int = None
) -> Dict[str, List[str]]:
    """
    Cluster items semantically and return representative samples for each cluster.
    
    Args:
        items: List of item descriptions.
        n_clusters: Number of clusters to generate (heuristic if None).
        
    Returns:
        Dictionary mapping cluster_id -> list of sample items.
        Example: { "Cluster 0": ["cafe po", "cafe graos"], "Cluster 1": ["caneta", "lapis"] }
    """
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import normalize
    
    if len(items) < 10:
        return {"Grupo Único": items}
        
    logging.info(f"Clustering {len(items)} items using Agglomerative Clustering...")
    
    # 1. Generate Embeddings
    embeddings = generate_embeddings(items)
    # Normalize for Cosine Similarity behavior with Euclidean distance
    embeddings = normalize(embeddings)
    
    # 2. Perform Agglomerative Clustering (Dynamic number of clusters)
    # distance_threshold=0.8 implies cosine_similarity < 0.2 approx?
    # sentence-embeddings are usually high similarity.
    # High threshold > 1.0 merges everything.
    # For normalized vectors, Euclidean dist range is 0 to 2.
    # dist = sqrt(2 * (1 - cos_sim))
    # If we want cos_sim > 0.6 (similar), then 1-0.6 = 0.4. 2*0.4=0.8. sqrt(0.8) approx 0.9.
    # Let's try distance_threshold=1.3 (approx 0.15 similarity) to allow broader groups.
    # 0.5 similarity was too strict (created 700 clusters).
    cluster_model = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1.3, 
        linkage='ward'
    ).fit(embeddings)
    
    labels = cluster_model.labels_
    n_clusters = len(set(labels))
    logging.info(f"Agglomerative Clustering discovered {n_clusters} clusters.")

    # 3. Find representative samples
    # We need to calculate centroids manually for Agglomerative
    centers = []
    unique_labels = sorted(list(set(labels)))
    
    for label in unique_labels:
        cluster_indices = np.where(labels == label)[0]
        cluster_embeddings = embeddings[cluster_indices]
        centroid = cluster_embeddings.mean(axis=0)
        centers.append(centroid)
        
    centers = np.array(centers)

    # 4. Find closest samples to each centroid
    nbrs = NearestNeighbors(n_neighbors=min(MAX_CLUSTER_SAMPLES, len(items)), metric='euclidean').fit(embeddings)
    
    # centers.shape is (n_clusters, embedding_dim)
    cluster_samples_indices = nbrs.kneighbors(centers, return_distance=False)
    
    results = {}
    for cluster_id, sample_indices in enumerate(cluster_samples_indices):
        # Retrieve actual text samples
        samples = [items[idx] for idx in sample_indices]
        # Remove duplicates in samples if any
        samples = list(dict.fromkeys(samples))
        results[f"Grupo {cluster_id + 1}"] = samples
        
    logging.info(f"Clustering completed. Generated {len(results)} groups.")
    return results


def strip_unspsc_code(text: str) -> str:
    """Remove UNSPSC code prefix from text (e.g., '50121501 - Chocolates' -> 'Chocolates')."""
    import re
    # Pattern: 8 digits followed by ' - '
    return re.sub(r'^\d{6,8}\s*[-–]\s*', '', str(text).strip())


def zero_shot_classify(
    items: List[str],
    categories: Any, # List[str] OR List[Dict]
    threshold: float = 0.45,
    unknown_label: str = "Outros"
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Classify items against a list of categories using Semantic Matching (Cosine Similarity).
    
    Args:
        items: List of item descriptions to classify.
        categories: List of target category names (N4) OR List of Dicts (if structured taxonomy).
                    If Dict, must contain keys 'N4' (target) and optionally 'N1','N2','N3' (context).
        threshold: Minimum similarity score (0.0 to 1.0) to accept a match.
        unknown_label: Label to assign if no match exceeds threshold.
        
    Returns:
        Tuple of (results_list, analytics_dict)
    """
    from sklearn.metrics.pairwise import cosine_similarity
    
    if not items or not categories:
        raise ValueError("Items and Categories must be provided.")
        
    logging.info(f"Semantic Classification: {len(items)} items vs {len(categories)} categories.")
    
    # Pre-process categories to extract target text for embedding
    # If categories is List[Dict], extract 'N4' (or 'N4_Nome') as target, keep full dict for result lookup
    target_categories: List[str] = []
    target_categories_clean: List[str] = []  # Without UNSPSC codes - for embedding
    category_metadata: List[Dict] = []
    
    if isinstance(categories[0], dict):
        # Structured Taxonomy
        for cat in categories:
            # Flexible key access (adjust as needed based on Excel parsing)
            n4_val = cat.get('N4', cat.get('N4_Nome', ''))
            target_categories.append(str(n4_val).strip())
            target_categories_clean.append(strip_unspsc_code(n4_val))
            category_metadata.append(cat)
    else:
        # Simple List of Strings
        target_categories = [str(c).strip() for c in categories]
        target_categories_clean = [strip_unspsc_code(c) for c in categories]
        category_metadata = [{"N4": c} for c in target_categories]

    logging.info(f"Sample categories (clean): {target_categories_clean[:5]}")
    
    # 1. Embed Categories (Target) - Using CLEAN names without codes
    cat_embeddings = generate_embeddings(target_categories_clean)
    
    # 2. Embed Items (Source)
    item_embeddings = generate_embeddings(items)
    
    # 3. Calculate Similarity Matrix
    similarity_matrix = cosine_similarity(item_embeddings, cat_embeddings)
    
    # 4. Find Best Matches
    best_match_indices = similarity_matrix.argmax(axis=1)
    best_match_scores = similarity_matrix.max(axis=1)
    
    results = []
    
    match_counts = {
        "Exact": 0,
        "Uncertain": 0,
        "Unmatched": 0
    }
    
    high_threshold = 0.75
    
    for i, item_text in enumerate(items):
        score = float(best_match_scores[i])
        cat_idx = best_match_indices[i]
        
        # Default empty result structure
        match_data = {
            "Description": item_text,
            "N1_Predicted": "",
            "N2_Predicted": "",
            "N3_Predicted": "",
            "N4_Predicted": "",
            "Confidence": score,
            "Match_Type": "Nenhum"
        }

        if score >= threshold:
            # Valid match found
            matched_meta = category_metadata[cat_idx]
            
            # Fill prediction data
            match_data["N4_Predicted"] = matched_meta.get("N4", matched_meta.get("N4_Nome",  target_categories[cat_idx]))
            match_data["N1_Predicted"] = matched_meta.get("N1", matched_meta.get("N1_Nome", ""))
            match_data["N2_Predicted"] = matched_meta.get("N2", matched_meta.get("N2_Nome", ""))
            match_data["N3_Predicted"] = matched_meta.get("N3", matched_meta.get("N3_Nome", ""))
            
            if score >= high_threshold:
                match_data["Match_Type"] = "Único"
                match_counts["Exact"] += 1
            else:
                match_data["Match_Type"] = "Ambíguo"
                match_counts["Uncertain"] += 1
        else:
            # No match
            match_data["N4_Predicted"] = unknown_label if unknown_label else ""
            match_counts["Unmatched"] += 1
            
        results.append(match_data)
        
    # 5. Build Analytics
    analytics = {
        "total_items": len(items),
        "total_categories": len(target_categories),
        "match_distribution": match_counts
    }
    
    logging.info("Zero-Shot classification completed.")
    return results, analytics
