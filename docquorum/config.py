import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LLM_URL = os.environ.get("DQ_LLM_URL", "http://localhost:8079/v1")
MODEL = os.environ.get("DQ_MODEL_NAME", "qwen3vl")
PARSER_URL = os.environ.get("DQ_PARSER_URL", "http://localhost:8081/v1")

DATA = Path(os.environ.get("DQ_EXTRACTBENCH_DATA", ROOT / "data" / "extractbench"))
PARSE_CACHE = Path(os.environ.get("DQ_PARSE_CACHE", ROOT / "cache" / "parse"))
RUNS = Path(os.environ.get("DQ_RUNS", ROOT / "runs"))


def _poppler(tool):
    d = os.environ.get("DQ_POPPLER_BIN")
    if d and (Path(d) / tool).exists():
        return str(Path(d) / tool)
    return shutil.which(tool) or tool


PDFTOTEXT, PDFTOPPM, PDFINFO = _poppler("pdftotext"), _poppler("pdftoppm"), _poppler("pdfinfo")
PDFFONTS, PDFIMAGES = _poppler("pdffonts"), _poppler("pdfimages")
