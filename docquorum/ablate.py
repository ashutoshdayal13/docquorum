"""
Switches that turn one part of the pipeline off, for the ablation study (benchmarks/ablations).
DQ_ABLATE is a comma-separated list of parts; unset, every part is on and nothing changes.

  replan         the reader makes one whole-document call and keeps what it returns
  schema_groups  the reader never reads the schema in groups (plan 2)
  recovery       no second call after a cut-off, looping, empty or key-skipping reply
  legends        list chunks are read without the legends copied from the opening pages
  colflow        the column reader is never selected
  ruled          the ruled-table reader is never selected
"""
import os

PARTS = ("replan", "schema_groups", "recovery", "legends", "colflow", "ruled")
OFF = frozenset(p for p in os.environ.get("DQ_ABLATE", "").split(",") if p)
if OFF - set(PARTS):
    raise ValueError(f"DQ_ABLATE: unknown parts {sorted(OFF - set(PARTS))}; known: {', '.join(PARTS)}")


def off(part):
    return part in OFF
