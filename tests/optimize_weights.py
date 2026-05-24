"""Test weights optimization."""
import sys
import os

project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
)
sys.path.insert(0, os.path.join(project_root, 'src'))


def optimize_example():
    """Example optimization run."""
    print("Optimization framework ready")


if __name__ == "__main__":
    optimize_example()
