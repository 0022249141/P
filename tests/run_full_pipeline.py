"""Run full analysis pipeline."""
import sys
import os
import json
import pandas as pd

project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
)
sys.path.insert(0, os.path.join(project_root, 'src'))

from market_engine import MarketDataEngine
from structure_engine import StructuralEngine


def main():
    """Run full pipeline analysis."""
    print("Full pipeline ready")


if __name__ == "__main__":
    main()
