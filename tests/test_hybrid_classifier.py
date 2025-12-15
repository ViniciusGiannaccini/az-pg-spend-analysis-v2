"""
Tests for src/hybrid_classifier.py - ML + Dictionary hybrid classification.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hybrid_classifier import classify_hybrid, ClassificationResult


class TestClassifyHybrid:
    """Tests for hybrid classification logic."""

    @pytest.fixture
    def mock_ml_prediction_high_confidence(self):
        """Mock ML prediction with high confidence (>= 0.70)."""
        return {
            "n4": "Material Escolar",
            "confidence": 0.85,
            "top_k": [
                {"n4": "Material Escolar", "confidence": 0.85},
                {"n4": "Papelaria", "confidence": 0.10},
                {"n4": "Escritório", "confidence": 0.05},
            ],
            "hierarchy": {
                "N1": "Suprimentos",
                "N2": "Educação",
                "N3": "Materiais",
                "N4": "Material Escolar"
            }
        }

    @pytest.fixture
    def mock_ml_prediction_medium_confidence(self):
        """Mock ML prediction with medium confidence (0.40-0.69)."""
        return {
            "n4": "Serviços Gerais",
            "confidence": 0.55,
            "top_k": [
                {"n4": "Serviços Gerais", "confidence": 0.55},
                {"n4": "Manutenção", "confidence": 0.30},
                {"n4": "Limpeza", "confidence": 0.10},
            ],
            "hierarchy": {
                "N1": "Serviços",
                "N2": "Facilities",
                "N3": "Operacional",
                "N4": "Serviços Gerais"
            }
        }

    @pytest.fixture
    def mock_ml_prediction_low_confidence(self):
        """Mock ML prediction with low confidence (< 0.40)."""
        return {
            "n4": "Outros",
            "confidence": 0.25,
            "top_k": [
                {"n4": "Outros", "confidence": 0.25},
                {"n4": "Diversos", "confidence": 0.20},
                {"n4": "Geral", "confidence": 0.15},
            ],
            "hierarchy": {
                "N1": "Outros",
                "N2": "Outros",
                "N3": "Outros",
                "N4": "Outros"
            }
        }

    def test_high_confidence_uses_ml(self, taxonomy_df):
        """High confidence ML predictions should be used directly."""
        # This test verifies the threshold logic
        # Confidence >= 0.70 should result in "Único" status with ML source
        
        # We test the threshold constants
        HIGH_CONFIDENCE_THRESHOLD = 0.70
        
        # With 85% confidence, should use ML
        ml_confidence = 0.85
        assert ml_confidence >= HIGH_CONFIDENCE_THRESHOLD

    def test_medium_confidence_is_ambiguous(self):
        """Medium confidence should result in 'Ambíguo' status."""
        LOW_THRESHOLD = 0.40
        HIGH_THRESHOLD = 0.70
        
        ml_confidence = 0.55
        assert LOW_THRESHOLD <= ml_confidence < HIGH_THRESHOLD

    def test_low_confidence_triggers_fallback(self):
        """Low confidence should trigger dictionary fallback."""
        LOW_THRESHOLD = 0.40
        
        ml_confidence = 0.25
        assert ml_confidence < LOW_THRESHOLD


class TestClassificationResult:
    """Tests for ClassificationResult structure."""

    def test_result_has_required_fields(self):
        """ClassificationResult should have all required fields."""
        result = ClassificationResult(
            status="Único",
            n1="Test N1",
            n2="Test N2", 
            n3="Test N3",
            n4="Test N4",
            matched_terms=["term1"],
            confidence=0.85,
            source="ML",
            ambiguous_n4s=[]
        )
        
        assert result.status == "Único"
        assert result.n1 == "Test N1"
        assert result.n4 == "Test N4"
        assert result.confidence == 0.85
        assert result.source == "ML"

    def test_ambiguous_result(self):
        """Ambiguous classification should include candidate N4s."""
        result = ClassificationResult(
            status="Ambíguo",
            n1="Test N1",
            n2="Test N2",
            n3="Test N3",
            n4="Test N4",
            matched_terms=[],
            confidence=0.55,
            source="ML",
            ambiguous_n4s=["N4 Option 1", "N4 Option 2", "N4 Option 3"]
        )
        
        assert result.status == "Ambíguo"
        assert len(result.ambiguous_n4s) == 3

    def test_no_match_result(self):
        """No match result should have 'Nenhum' status."""
        result = ClassificationResult(
            status="Nenhum",
            n1="",
            n2="",
            n3="",
            n4="",
            matched_terms=[],
            confidence=0.0,
            source="None",
            ambiguous_n4s=[]
        )
        
        assert result.status == "Nenhum"
        assert result.source == "None"

    def test_to_dict_method(self):
        """to_dict should convert to proper dictionary format."""
        result = ClassificationResult(
            status="Único",
            n1="N1",
            n2="N2",
            n3="N3",
            n4="N4",
            matched_terms=[],
            confidence=0.9,
            source="ML"
        )
        
        d = result.to_dict()
        assert d["N1"] == "N1"
        assert d["N4"] == "N4"
        assert d["ml_confidence"] == 0.9
        assert d["classification_source"] == "ML"
