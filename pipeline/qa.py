"""[8] QA GATE — policy + fact safety before publish.

Checks: (a) every script claim cites a grounded source; (b) no monetization-risk
content; (c) footage sources are all allowed. Start human-in-loop, then automate.
"""
from __future__ import annotations


def check(job) -> bool:
    """Return True if safe to publish. TODO: implement checks."""
    raise NotImplementedError("Implement fact-coverage + policy scan.")
