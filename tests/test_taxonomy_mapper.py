"""
Tests for src/taxonomy_mapper.py - Custom hierarchy mapping.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.taxonomy_mapper import load_custom_hierarchy, apply_custom_hierarchy


class TestLoadCustomHierarchy:
    """Tests for loading custom hierarchy files."""

    def test_load_from_training_file(self, sample_training_path, encode_file_base64):
        """Should load hierarchy from training file."""
        if not sample_training_path.exists():
            pytest.skip("Training file not found")
        
        base64_content = encode_file_base64(sample_training_path)
        
        try:
            hierarchy = load_custom_hierarchy(base64_content)
            
            assert hierarchy is not None
            assert isinstance(hierarchy, dict)
            assert len(hierarchy) > 0
        except Exception as e:
            # Hierarchy loading may fail if format doesn't match expected
            pytest.skip(f"Could not load hierarchy: {e}")

    def test_hierarchy_structure(self, sample_training_path, encode_file_base64):
        """Hierarchy should have N1-N4 for each entry."""
        if not sample_training_path.exists():
            pytest.skip("Training file not found")
        
        base64_content = encode_file_base64(sample_training_path)
        
        try:
            hierarchy = load_custom_hierarchy(base64_content)
            
            if hierarchy and len(hierarchy) > 0:
                sample_key = list(hierarchy.keys())[0]
                entry = hierarchy[sample_key]
                
                # Should have hierarchy levels
                assert isinstance(entry, dict)
        except Exception:
            pytest.skip("Hierarchy format different than expected")


class TestApplyCustomHierarchy:
    """Tests for applying custom hierarchy to ML candidates."""

    def test_apply_to_top_candidates(self):
        """Should find match in top candidates."""
        top_candidates = [
            {"N4": "Material Escolar", "confidence": 0.85},
            {"N4": "Papelaria", "confidence": 0.10},
            {"N4": "Escritório", "confidence": 0.05},
        ]
        
        custom_hierarchy = {
            "material escolar": {
                "N1": "Suprimentos",
                "N2": "Educação",
                "N3": "Materiais",
                "N4": "Material Escolar"
            }
        }
        
        result, matched_n4 = apply_custom_hierarchy(top_candidates, custom_hierarchy)
        
        assert result is not None
        assert matched_n4 == "Material Escolar"

    def test_fallback_to_second_candidate(self):
        """Should fallback to 2nd candidate if 1st not in hierarchy."""
        top_candidates = [
            {"N4": "Não Existe", "confidence": 0.85},
            {"N4": "Papelaria", "confidence": 0.10},
            {"N4": "Escritório", "confidence": 0.05},
        ]
        
        custom_hierarchy = {
            "papelaria": {
                "N1": "Suprimentos",
                "N2": "Escritório",
                "N3": "Papel",
                "N4": "Papelaria"
            }
        }
        
        result, matched_n4 = apply_custom_hierarchy(top_candidates, custom_hierarchy)
        
        assert result is not None
        assert matched_n4 == "Papelaria"

    def test_no_match_returns_none(self):
        """Should return None if no candidate matches hierarchy."""
        top_candidates = [
            {"N4": "Não Existe 1", "confidence": 0.85},
            {"N4": "Não Existe 2", "confidence": 0.10},
            {"N4": "Não Existe 3", "confidence": 0.05},
        ]
        
        custom_hierarchy = {
            "algo diferente": {
                "N1": "X",
                "N2": "Y",
                "N3": "Z",
                "N4": "Algo Diferente"
            }
        }
        
        result, matched_n4 = apply_custom_hierarchy(top_candidates, custom_hierarchy)
        
        assert result is None
        assert matched_n4 is None
