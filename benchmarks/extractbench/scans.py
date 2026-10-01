"""Documents without a text layer, from the documents themselves (no annotation).

    python scans.py <split>                      line 1: every such document; line 2: those of
                                                 <= 12 pages (they fit one call)
    python scans.py --copy <src> <dst> <a,b,..>  copy those documents' readings from src to dst
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))       # the docquorum package
from docquorum.extractbench import scans  # noqa: E402

if sys.argv[1] == "--copy":
    src, dst = Path(sys.argv[2]), Path(sys.argv[3])
    for d in sys.argv[4].split(","):
        if (src / f"{d}.json").exists():
            shutil.copy(src / f"{d}.json", dst)
else:
    every, short = scans(sys.argv[1])
    print(",".join(every))
    print(",".join(short))
