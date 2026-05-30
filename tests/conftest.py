from pathlib import Path

_HERE = Path(__file__).parent

# Legacy/manual smoke scripts.
# These files execute heavy market-processing code at import time and are not
# safe for normal pytest collection. They should be run manually only when needed.
collect_ignore = [
    str(_HERE / "quick_test.py"),
    str(_HERE / "test_layer1_2.py"),
]
