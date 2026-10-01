"""
DocQuorum: agentic document extraction by a quorum of grounded readings.

  tools/    what the agents act with: PDF text and images, the MinerU parser, the model call,
            schema helpers, row counting, page geometry
  agents/   the readers: the reader agent (plan / act / observe), the one-shot reader, and the
            layout agent with its column-flow and ruled-table readers; their prompts
  checks/   deterministic repairs and checks of a reading against the schema and the page text
  quorum.py the reading the others agree with most
  extract.py the whole pipeline on one document
"""
__version__ = "1.1.0"
