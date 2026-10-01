"""
Paths and endpoints. Each can be overridden with the environment variable named beside it;
every other setting of the measured configuration is a constant in the module that uses it.
"""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent              # the project folder

# model endpoints (OpenAI-compatible, e.g. vLLM)
LLM_URL = os.environ.get("DQ_LLM_URL", "http://localhost:8079/v1")      # the extraction model
MODEL = os.environ.get("DQ_MODEL_NAME", "qwen3vl")                        # its served name
PARSER_URL = os.environ.get("DQ_PARSER_URL", "http://localhost:8081/v1")  # MinerU2.5

# data and caches
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
