import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from docquorum.extractbench import scans

if sys.argv[1] == "--copy":
    src, dst = Path(sys.argv[2]), Path(sys.argv[3])
    for d in sys.argv[4].split(","):
        if (src / f"{d}.json").exists():
            shutil.copy(src / f"{d}.json", dst)
else:
    every, short = scans(sys.argv[1])
    print(",".join(every))
    print(",".join(short))
