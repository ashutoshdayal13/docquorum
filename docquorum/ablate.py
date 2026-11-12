import os

PARTS = ("replan", "schema_groups", "recovery", "legends", "colflow", "ruled")
OFF = frozenset(p for p in os.environ.get("DQ_ABLATE", "").split(",") if p)
if OFF - set(PARTS):
    raise ValueError(
        f"DQ_ABLATE: unknown parts {sorted(OFF - set(PARTS))}; known: {', '.join(PARTS)}"
    )


def off(part):
    return part in OFF
