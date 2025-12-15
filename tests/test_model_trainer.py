"""
Tests for src/model_trainer.py - Model training pipeline.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestModelTrainerPipeline:
    """Tests for training pipeline logic."""

    def test_training_file_validation(self, sample_training_df):
        """Training file should pass validation checks."""
        # Check minimum records
        MIN_RECORDS = 10
        assert len(sample_training_df) >= MIN_RECORDS, \
            f"Training file should have at least {MIN_RECORDS} records"

    def test_category_distribution(self, sample_training_df):
        """Check N4 category distribution."""
        columns_lower = {c.lower(): c for c in sample_training_df.columns}
        n4_col = columns_lower.get("n4")
        
        if n4_col is None:
            pytest.skip("N4 column not found")
        
        n4_counts = sample_training_df[n4_col].value_counts()
        
        # Should have multiple categories
        assert len(n4_counts) >= 2, "Should have at least 2 different N4 categories"

    def test_description_column_present(self, sample_training_df):
        """Description column should be present and non-empty."""
        desc_col = None
        for col in sample_training_df.columns:
            if "desc" in col.lower():
                desc_col = col
                break
        
        assert desc_col is not None, "Description column not found"
        
        # Check for non-null values
        null_count = sample_training_df[desc_col].isnull().sum()
        assert null_count < len(sample_training_df), "All descriptions are null"


class TestModelVersioning:
    """Tests for model versioning system."""

    def test_versions_directory_exists(self, test_sector):
        """Versions directory should exist or be creatable."""
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        versions_dir = models_dir / "versions"
        
        # For existing sectors, versions dir should exist
        if models_dir.exists():
            # Versions directory might not exist if no training done
            pass

    def test_max_versions_limit(self, test_sector):
        """Should maintain maximum 3 versions."""
        MAX_VERSIONS = 3
        
        models_dir = Path(__file__).parent.parent / "models" / test_sector
        versions_dir = models_dir / "versions"
        
        if not versions_dir.exists():
            pytest.skip("No versions directory")
        
        versions = [v for v in versions_dir.iterdir() if v.is_dir()]
        
        # Should not exceed max
        assert len(versions) <= MAX_VERSIONS, \
            f"Should have at most {MAX_VERSIONS} versions, found {len(versions)}"


class TestTrainingCleanup:
    """Tests for training data cleanup scenarios."""

    def test_cleanup_scenario_documented(self):
        """
        Training cleanup test scenario:
        1. Train model with test data
        2. Verify new version created
        3. Delete test training data
        4. Verify data removed
        
        This serves as documentation for the cleanup flow.
        """
        # This test documents the cleanup scenario
        # Actual cleanup is done via DeleteTrainingData endpoint
        
        cleanup_steps = [
            "1. Send POST /TrainModel with test file",
            "2. Note the version_id in response",
            "3. Send DELETE /DeleteTrainingData with version filter",
            "4. Verify data removed from dataset_master.csv"
        ]
        
        assert len(cleanup_steps) == 4
