"""
Pytest configuration and shared fixtures for Spend Analysis tests.
"""
import os
import sys
import pytest
import pandas as pd
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Return the fixtures directory path."""
    return FIXTURES_DIR


@pytest.fixture
def sample_items_path():
    """Path to sample items Excel file for classification testing."""
    return FIXTURES_DIR / "sample_items.xlsx"


@pytest.fixture
def sample_training_path():
    """Path to sample training Excel file."""
    return FIXTURES_DIR / "sample_training.xlsx"


@pytest.fixture
def sample_items_df(sample_items_path):
    """Load sample items as DataFrame."""
    return pd.read_excel(sample_items_path)


@pytest.fixture
def sample_training_df(sample_training_path):
    """Load sample training data as DataFrame."""
    return pd.read_excel(sample_training_path)


@pytest.fixture
def taxonomy_path():
    """Path to Spend_Taxonomy.xlsx dictionary."""
    return PROJECT_ROOT / "data" / "taxonomy" / "Spend_Taxonomy.xlsx"


@pytest.fixture
def taxonomy_df(taxonomy_path):
    """Load taxonomy dictionary for Educacional sector."""
    return pd.read_excel(taxonomy_path, sheet_name="DIC_EDUCACIONAL")


@pytest.fixture
def sample_descriptions():
    """Sample descriptions for quick unit tests."""
    return [
        "Material escolar para sala de aula",
        "Livros didáticos de matemática",
        "Serviços de limpeza predial",
        "Manutenção de ar condicionado",
        "Computadores para laboratório",
        "Café para reuniões",
    ]


@pytest.fixture
def test_sector():
    """Test sector name."""
    return "educacional"


# Base64 encoding helpers
import base64

@pytest.fixture
def encode_file_base64():
    """Helper function to encode file to base64."""
    def _encode(filepath):
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return _encode
