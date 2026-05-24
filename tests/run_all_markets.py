"""Run analysis on all markets."""
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
    """Run analysis on all available markets."""
    data_dir = os.path.join(project_root, 'data')
    results = {}

    for file in os.listdir(data_dir):
        if file.endswith('.csv') and 'signals' not in file:
            print(f"Processing {file}...")
            filepath = os.path.join(data_dir, file)

            try:
                engine = MarketDataEngine.from_custom_csv(filepath)
                struct = StructuralEngine(engine)
                struct.detect_swings()
                results[file] = {
                    'status': 'success',
                    'candles': len(engine.df)
                }
            except Exception as e:
                results[file] = {'status': 'error', 'message': str(e)}

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
