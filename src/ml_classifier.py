"""
ML Classifier for Spend Analysis.

This module provides the ML-based classification functionality with:
- Model loading and caching
- Prediction with confidence scores
- Complete taxonomy hierarchy (N1, N2, N3, N4) for each prediction
"""

import joblib
import json
import os
from typing import List, Tuple, Dict, Optional
import numpy as np
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.preprocessing import normalize_text


# Global cache for loaded models (per sector)
_MODEL_CACHE = {}


def clear_model_cache(sector: str = None):
    """
    Clear the model cache to force reloading on next prediction.
    
    Args:
        sector: If provided, clear only this sector's cache. 
                If None, clear all cached models.
    """
    global _MODEL_CACHE
    if sector:
        sector = sector.lower().strip()
        if sector in _MODEL_CACHE:
            del _MODEL_CACHE[sector]
            print(f"Cleared model cache for sector '{sector}'")
    else:
        _MODEL_CACHE = {}
        print("Cleared all model caches")


def load_model(sector: str = "varejo", models_dir: str = "models") -> Tuple:
    """
    Load trained ML model artifacts for a specific sector with caching.
    
    Loads:
    - TF-IDF vectorizer
    - Logistic Regression classifier
    - Label encoder (N4 categories)
    - N4 hierarchy mapping (N4 -> N1, N2, N3)
    
    Args:
        sector: Sector name (e.g., 'varejo', 'industrial'). Models are loaded from models/{sector}/
        models_dir: Base directory containing sector subdirectories.
    
    Returns:
        Tuple of (vectorizer, classifier, label_encoder, hierarchy_mapping)
    """
    # Normalize sector name (lowercase for consistency)
    sector = sector.lower().strip()
    
    # Return cached models if already loaded for this sector
    if sector in _MODEL_CACHE and all(v is not None for v in _MODEL_CACHE[sector].values()):
        return (
            _MODEL_CACHE[sector]['vectorizer'],
            _MODEL_CACHE[sector]['classifier'],
            _MODEL_CACHE[sector]['label_encoder'],
            _MODEL_CACHE[sector]['hierarchy']
        )
    
    # Sector-specific model directory
    sector_model_dir = os.path.join(models_dir, sector)
    
    if not os.path.exists(sector_model_dir):
        raise FileNotFoundError(
            f"Model directory for sector '{sector}' not found: {sector_model_dir}. "
            f"Please train models for this sector first."
        )
    
    print(f"Loading ML model for sector '{sector}' from {sector_model_dir}/...")
    
    # Initialize cache for this sector
    if sector not in _MODEL_CACHE:
        _MODEL_CACHE[sector] = {
            'vectorizer': None,
            'classifier': None,
            'label_encoder': None,
            'hierarchy': None
        }
    
    # Load vectorizer
    vectorizer_path = os.path.join(sector_model_dir, "tfidf_vectorizer.pkl")
    _MODEL_CACHE[sector]['vectorizer'] = joblib.load(vectorizer_path)
    print(f"  [SUCCESS] Loaded vectorizer")
    
    # Load classifier
    classifier_path = os.path.join(sector_model_dir, "classifier.pkl")
    _MODEL_CACHE[sector]['classifier'] = joblib.load(classifier_path)
    print(f"  [SUCCESS] Loaded classifier")
    
    # Load label encoder
    encoder_path = os.path.join(sector_model_dir, "label_encoder.pkl")
    _MODEL_CACHE[sector]['label_encoder'] = joblib.load(encoder_path)
    print(f"  [SUCCESS] Loaded label encoder ({len(_MODEL_CACHE[sector]['label_encoder'].classes_)} classes)")
    
    # Load hierarchy mapping
    hierarchy_path = os.path.join(sector_model_dir, "n4_hierarchy.json")
    with open(hierarchy_path, 'r', encoding='utf-8') as f:
        _MODEL_CACHE[sector]['hierarchy'] = json.load(f)
    print(f"  [SUCCESS] Loaded hierarchy mapping")
    
    print(f"ML model for sector '{sector}' loaded successfully!")
    
    return (
        _MODEL_CACHE[sector]['vectorizer'],
        _MODEL_CACHE[sector]['classifier'],
        _MODEL_CACHE[sector]['label_encoder'],
        _MODEL_CACHE[sector]['hierarchy']
    )


def predict(
    texts: List[str],
    sector: str = "varejo",
    vectorizer=None,
    classifier=None,
    label_encoder=None,
    hierarchy=None,
    top_k: int = 3
) -> List[Dict]:
    """
    Predict N4 categories for a list of texts using the ML model.
    
    Args:
        texts: List of item descriptions (raw or normalized).
        sector: Sector name for model selection.
        vectorizer: TF-IDF vectorizer (loaded if None).
        classifier: Trained classifier (loaded if None).
        label_encoder: Label encoder (loaded if None).
        hierarchy: N4 hierarchy mapping (loaded if None).
        top_k: Number of top predictions to return for ambiguous cases.
    
    Returns:
        List of dictionaries, one per text, containing:
        - n4_predicted: Top predicted N4 category
        - confidence: Probability of top prediction (0-1)
        - n1, n2, n3: Hierarchy levels for the predicted N4
        - top_candidates: List of top K (N4, confidence, N1, N2, N3) tuples
    """
    # Load models if not provided
    if any(x is None for x in [vectorizer, classifier, label_encoder, hierarchy]):
        vectorizer, classifier, label_encoder, hierarchy = load_model(sector=sector)
    
    # Normalize texts
    texts_normalized = [normalize_text(text) for text in texts]
    
    # Vectorize
    X = vectorizer.transform(texts_normalized)
    
    # Predict probabilities
    probas = classifier.predict_proba(X)
    
    # Build results
    results = []
    for i, text_probas in enumerate(probas):
        # Get top K predictions
        top_k_indices = np.argsort(text_probas)[::-1][:top_k]
        top_k_n4s = label_encoder.inverse_transform(top_k_indices)
        top_k_probas = text_probas[top_k_indices]
        
        # Top prediction
        n4_predicted = top_k_n4s[0]
        confidence = top_k_probas[0]
        
        # Get hierarchy for top prediction
        n4_hierarchy = hierarchy.get(n4_predicted, {})
        n1 = n4_hierarchy.get('N1', '')
        n2 = n4_hierarchy.get('N2', '')
        n3 = n4_hierarchy.get('N3', '')
        
        # Build top candidates with hierarchy
        top_candidates = []
        for n4, prob in zip(top_k_n4s, top_k_probas):
            n4_hier = hierarchy.get(n4, {})
            top_candidates.append({
                'N4': n4,
                'confidence': float(prob),
                'N1': n4_hier.get('N1', ''),
                'N2': n4_hier.get('N2', ''),
                'N3': n4_hier.get('N3', '')
            })
        
        results.append({
            'n4_predicted': n4_predicted,
            'confidence': float(confidence),
            'N1': n1,
            'N2': n2,
            'N3': n3,
            'N4': n4_predicted,
            'top_candidates': top_candidates
        })
    
    return results


def predict_single(
    text: str,
    sector: str = "varejo",
    vectorizer=None,
    classifier=None,
    label_encoder=None,
    hierarchy=None,
    top_k: int = 3
) -> Dict:
    """
    Predict N4 category for a single text.
    
    Convenience wrapper around predict() for single texts.
    
    Args:
        text: Item description.
        sector: Sector name for model selection.
        vectorizer: TF-IDF vectorizer (loaded if None).
        classifier: Trained classifier (loaded if None).
        label_encoder: Label encoder (loaded if None).
        hierarchy: N4 hierarchy mapping (loaded if None).
        top_k: Number of top predictions to return.
    
    Returns:
        Dictionary with prediction results (same format as predict()).
    """
    results = predict([text], sector, vectorizer, classifier, label_encoder, hierarchy, top_k)
    return results[0]


if __name__ == "__main__":
    # Test the classifier
    print("Testing ML Classifier...")
    print("=" * 60)
    
    # Example texts
    test_texts = [
        "CAFE GRAOS 1KG",
        "ETIQUETA ADESIVA BRANCA",
        "FRETE RODOVIARIO SAO PAULO"
    ]
    
    print("\nTest predictions:")
    print("-" * 60)
    
    for text in test_texts:
        result = predict_single(text)
        print(f"\nText: {text}")
        print(f"Predicted N4: {result['n4_predicted']}")
        print(f"Confidence: {result['confidence']:.4f}")
        print(f"Hierarchy: {result['N1']} > {result['N2']} > {result['N3']} > {result['N4']}")
        print(f"Top 3 candidates:")
        for j, cand in enumerate(result['top_candidates'], 1):
            print(f"  {j}. {cand['N4']} (conf: {cand['confidence']:.4f})")
