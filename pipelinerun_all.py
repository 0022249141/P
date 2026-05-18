import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

SIGNALS = BASE / "data" / "signals.csv"
MARKET = BASE / "data_clean" / "abshodeNaghdi-1.csv"
OUTPUT = BASE / "result.json"

cmd = [
    "python",
    "-m",
    "smc_validation.cli",
    "--signals", str(SIGNALS),
    "--market", f"abshodeh={MARKET}",
    "--output", str(OUTPUT)
]

print("RUNNING PIPELINE...")
subprocess.run(cmd, cwd=str(BASE))
