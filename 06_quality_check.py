import subprocess

steps = [
    "01_fix_data.py",
    "02_resample_mtf.py",
    "03_structure.py",
    "04_liquidity.py",
    "05_sessions.py"
]

for s in steps:

    print(f"\nRUNNING {s}\n")

    subprocess.run(
        ["python", f"institutional_pipeline/{s}"]
    )