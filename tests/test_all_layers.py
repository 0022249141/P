"""Test all analysis layers."""
import sys
import os

import pandas as pd

project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
)
sys.path.insert(0, os.path.join(project_root, 'src'))

from market_engine import MarketDataEngine
from structure_engine import StructuralEngine


def test_market_engine():
    """Test market data engine."""
    print("Market engine test")


def test_structure():
    """Test structural analysis."""
    print("Structure engine test")


if __name__ == "__main__":
    test_market_engine()
    test_structure()
