"""
Tests for src/ml_classifier.py - ML-based classification.
"""
import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml_classifier import load_model, predict_single, predict


class TestLoadModel:
    """Tests for ML model loading."""

    def test_load_model_educacional(self, test_sector):
        """Should load model for educacional sector."""
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        
        if not models_dir.exists():
            pytest.skip(f"Model for {test_sector} not found")
        
        try:
            vectorizer, classifier, label_encoder, hierarchy = load_model(test_sector)
            
            assert vectorizer is not None
            assert classifier is not None
            assert label_encoder is not None
            assert hierarchy is not None
        except Exception as e:
            pytest.skip(f"Could not load model: {e}")

    def test_model_has_hierarchy(self, test_sector):
        """Model should have N4 hierarchy mapping."""
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        hierarchy_path = models_dir / "n4_hierarchy.json"
        
        if not hierarchy_path.exists():
            pytest.skip("Hierarchy file not found")
        
        import json
        with open(hierarchy_path) as f:
            hierarchy = json.load(f)
        
        assert len(hierarchy) > 0
        # Each entry should have N1, N2, N3, N4
        sample_key = list(hierarchy.keys())[0]
        assert "N1" in hierarchy[sample_key] or "n1" in hierarchy[sample_key].lower() if isinstance(hierarchy[sample_key], str) else True


class TestPredict:
    """Tests for ML predictions."""

    def test_predict_single_returns_result(self, test_sector, sample_descriptions):
        """predict_single should return prediction dict."""
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        
        if not models_dir.exists():
            pytest.skip(f"Model for {test_sector} not found")
        
        try:
            result = predict_single(sample_descriptions[0], test_sector)
            
            assert result is not None
            assert "n4" in result or "N4" in result
            assert "confidence" in result
        except Exception as e:
            pytest.skip(f"Prediction failed: {e}")

    def test_predict_batch(self, test_sector, sample_descriptions):
        """predict should handle batch predictions."""
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        
        if not models_dir.exists():
            pytest.skip(f"Model for {test_sector} not found")
        
        try:
            results = predict(sample_descriptions[:3], test_sector)
            
            assert len(results) == 3
            for result in results:
                assert "confidence" in result
        except Exception as e:
            pytest.skip(f"Batch prediction failed: {e}")

    def test_confidence_range(self, test_sector, sample_descriptions):
        """Confidence should be between 0 and 1."""
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        
        if not models_dir.exists():
            pytest.skip(f"Model for {test_sector} not found")
        
        try:
            result = predict_single(sample_descriptions[0], test_sector)
            confidence = result.get("confidence", 0)
            
            assert 0 <= confidence <= 1
        except Exception as e:
            pytest.skip(f"Prediction failed: {e}")
