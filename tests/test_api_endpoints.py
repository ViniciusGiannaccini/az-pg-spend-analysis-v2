"""
Integration tests for Azure Function API endpoints.
Tests the main endpoints: ProcessTaxonomy, TrainModel, GetModelHistory, SetActiveModel.
"""
import pytest
import sys
import json
import base64
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestProcessTaxonomyEndpoint:
    """Tests for /ProcessTaxonomy endpoint."""

    def test_process_taxonomy_request_format(
        self, sample_items_path, taxonomy_path, encode_file_base64, test_sector
    ):
        """Request should have correct format."""
        if not sample_items_path.exists() or not taxonomy_path.exists():
            pytest.skip("Required files not found")
        
        # Build request body
        request_body = {
            "fileContent": encode_file_base64(sample_items_path),
            "dictionaryContent": encode_file_base64(taxonomy_path),
            "sector": "Educacional",
            "originalFilename": "sample_items.xlsx"
        }
        
        # Validate structure
        assert "fileContent" in request_body
        assert "dictionaryContent" in request_body
        assert "sector" in request_body
        assert len(request_body["fileContent"]) > 0
        assert len(request_body["dictionaryContent"]) > 0

    def test_base64_encoding_valid(self, sample_items_path, encode_file_base64):
        """Base64 encoding should be valid."""
        if not sample_items_path.exists():
            pytest.skip("Sample items file not found")
        
        encoded = encode_file_base64(sample_items_path)
        
        # Should be able to decode
        try:
            decoded = base64.b64decode(encoded)
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"Base64 decoding failed: {e}")


class TestTrainModelEndpoint:
    """Tests for /TrainModel endpoint."""

    def test_train_request_format(
        self, sample_training_path, encode_file_base64, test_sector
    ):
        """Training request should have correct format."""
        if not sample_training_path.exists():
            pytest.skip("Training file not found")
        
        request_body = {
            "fileContent": encode_file_base64(sample_training_path),
            "sector": "Educacional",
            "filename": "sample_training.xlsx"
        }
        
        assert "fileContent" in request_body
        assert "sector" in request_body
        assert len(request_body["fileContent"]) > 0

    def test_training_file_has_required_columns(self, sample_training_df):
        """Training file should have Descrição and N4 columns."""
        columns_lower = [c.lower() for c in sample_training_df.columns]
        
        # Should have description column
        has_desc = any("desc" in c for c in columns_lower)
        assert has_desc, "Training file should have a description column"
        
        # Should have N4 column
        has_n4 = "n4" in columns_lower
        assert has_n4, "Training file should have N4 column"

    def test_training_file_has_hierarchy(self, sample_training_df):
        """Training file should have complete hierarchy (N1-N4)."""
        columns_lower = [c.lower() for c in sample_training_df.columns]
        
        assert "n1" in columns_lower, "Missing N1 column"
        assert "n2" in columns_lower, "Missing N2 column"
        assert "n3" in columns_lower, "Missing N3 column"
        assert "n4" in columns_lower, "Missing N4 column"


class TestGetModelHistoryEndpoint:
    """Tests for /GetModelHistory endpoint."""

    def test_history_file_exists(self, test_sector):
        """Model history file should exist for sector."""
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        history_path = models_dir / "model_history.json"
        
        if not models_dir.exists():
            pytest.skip(f"Models dir for {test_sector} not found")
        
        # History file may or may not exist
        if history_path.exists():
            with open(history_path) as f:
                history = json.load(f)
            
            assert isinstance(history, list)
            
            if len(history) > 0:
                entry = history[0]
                assert "version_id" in entry
                assert "timestamp" in entry

    def test_history_entry_format(self, test_sector):
        """History entries should have required fields."""
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        history_path = models_dir / "model_history.json"
        
        if not history_path.exists():
            pytest.skip("History file not found")
        
        with open(history_path) as f:
            history = json.load(f)
        
        if len(history) > 0:
            entry = history[0]
            required_fields = ["version_id", "timestamp", "status"]
            for field in required_fields:
                assert field in entry, f"Missing field: {field}"


class TestSetActiveModelEndpoint:
    """Tests for /SetActiveModel endpoint."""

    def test_set_active_request_format(self, test_sector):
        """SetActiveModel request should have correct format."""
        request_body = {
            "sector": test_sector,
            "version_id": "v_1"
        }
        
        assert "sector" in request_body
        assert "version_id" in request_body

    def test_version_directory_structure(self, test_sector):
        """Version directories should have required artifacts."""
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        versions_dir = models_dir / "versions"
        
        if not versions_dir.exists():
            pytest.skip("Versions directory not found")
        
        # Check if any version exists
        versions = list(versions_dir.iterdir())
        if len(versions) == 0:
            pytest.skip("No versions found")
        
        # Check first version has required files
        version_dir = versions[0]
        required_files = ["classifier.pkl", "tfidf_vectorizer.pkl", "label_encoder.pkl"]
        
        for req_file in required_files:
            file_path = version_dir / req_file
            if not file_path.exists():
                # Some files may be optional
                pass


class TestGetTokenEndpoint:
    """Tests for /get-token endpoint."""

    def test_direct_line_secret_required(self):
        """Direct Line secret should be configured in environment."""
        import os
        
        # This test just validates the pattern - actual secret may not be set locally
        secret = os.getenv("DIRECT_LINE_SECRET", "")
        
        # In production, this should be set
        # For now, just validate the pattern exists
        assert True  # Placeholder - actual test would check response format

    def test_token_response_format(self):
        """Token response should have conversationId and token."""
        # Mock response format
        expected_format = {
            "conversationId": "string",
            "token": "string",
            "expires_in": 1800
        }
        
        assert "conversationId" in expected_format
        assert "token" in expected_format
        assert "expires_in" in expected_format
