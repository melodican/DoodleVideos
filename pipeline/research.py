"""[2] RESEARCH — the GROUNDING step that keeps the channel monetizable.

For the chosen topic, gather 3-5 authoritative sources (NASA/ESA/STScI/peer
press) and extract verifiable facts with citations. The script MUST only assert
claims traceable to these. Sensational framing is fine; fabricated facts are not.
"""
from __future__ import annotations


def gather(topic: dict) -> list[dict]:
    """Return [{claim, source_url, source_name}]. TODO: implement retrieval."""
    raise NotImplementedError("Implement source retrieval + fact extraction.")
