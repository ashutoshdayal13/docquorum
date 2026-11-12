import os
from pathlib import Path

from docquorum import config as C

os.environ.setdefault("DQ_ONESHOT_URL", C.LLM_URL[:-3] if C.LLM_URL.endswith("/v1") else C.LLM_URL)
if Path(C.PDFTOPPM).is_absolute():
    os.environ["PATH"] = str(Path(C.PDFTOPPM).parent) + os.pathsep + os.environ.get("PATH", "")


def provider():
    from extract_bench.inference.providers.extract.vllm_extract import VLLMExtractProvider

    return VLLMExtractProvider(
        "vllm_extract",
        {
            "model": C.MODEL,
            "endpoint_env_var": "DQ_ONESHOT_URL",
            "additional_properties_false": True,
            "max_tokens": 32768,
            "dpi": 150,
            "timeout_s": 3600,
            "structured_output": False,
        },
    )


def read(pdf, schema, prov=None):
    prov = prov or provider()
    raw = prov._call_api_fitting_context(
        prov._prepare_schema(schema), prov._render_page_images(Path(pdf))
    )
    return raw.get("data")


def main():
    import json
    import sys
    from concurrent.futures import ThreadPoolExecutor
    from docquorum import extractbench as EB

    split, names, out = sys.argv[1], set(sys.argv[2].split(",")), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    prov = provider()

    def one(rec):
        name = EB.name_of(rec)
        try:
            (out / f"{name}.json").write_text(
                json.dumps(read(EB.pdf_of(rec), rec["data_schema"], prov))
            )
            print(f"  {name[:40]:40s} ok", flush=True)
        except Exception as e:
            print(f"  {name[:40]:40s} FAILED {type(e).__name__}: {str(e)[:120]}", flush=True)

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(one, [r for r in EB.load_records(split) if EB.name_of(r) in names]))


if __name__ == "__main__":
    main()
