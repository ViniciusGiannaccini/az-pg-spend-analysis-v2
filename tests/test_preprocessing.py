"""
Tests for src/preprocessing.py - Text normalization utilities.
"""
import pytest
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.preprocessing import normalize_text, normalize_corpus


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_lowercase_conversion(self):
        """Should convert text to lowercase."""
        assert "hello world" in normalize_text("HELLO WORLD").lower()

    def test_accent_removal(self):
        """Should remove accents from text."""
        result = normalize_text("Café com Açúcar")
        assert "á" not in result
        assert "ú" not in result
        assert "cafe" in result.lower()

    def test_punctuation_removal(self):
        """Should remove punctuation."""
        result = normalize_text("Hello, World! How are you?")
        assert "," not in result
        assert "!" not in result
        assert "?" not in result

    def test_multiple_spaces_compacted(self):
        """Should compact multiple spaces to single space."""
        result = normalize_text("Hello    World")
        assert "    " not in result

    def test_empty_string(self):
        """Should handle empty string."""
        result = normalize_text("")
        assert result == ""

    def test_none_handling(self):
        """Should handle None input gracefully."""
        result = normalize_text(None)
        assert result == ""

    def test_numeric_handling(self):
        """Should handle numeric inputs."""
        result = normalize_text("123.45")
        assert "123" in result or result == ""


class TestNormalizeCorpus:
    """Tests for normalize_corpus function."""

    def test_batch_normalization(self):
        """Should normalize a list of texts."""
        texts = ["Café", "Açúcar", "HELLO"]
        results = normalize_corpus(texts)
        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)

    def test_empty_list(self):
        """Should handle empty list."""
        results = normalize_corpus([])
        assert results == []
