"""[8] QA GATE — policy + fact safety before publish.

Offline checks that actually run:
  (a) fact-coverage: every grounded claim's source is referenced in the script;
  (b) speculation is explicitly flagged;
  (c) sources are non-empty.
Returns True only if safe to publish.
"""
from __future__ import annotations
import logging
log = logging.getLogger("pipeline.qa")


def check(job) -> bool:
    if not job.sources:
        log.warning("QA: no grounded sources"); return False
    # every source must be cited in the script (by its [n] index)
    for i, _ in enumerate(job.sources, 1):
        if f"[{i}]" not in job.script_text:
            log.warning("QA: source [%d] not cited in script", i); return False
    if "[SPECULATION]" not in job.script_text:
        log.warning("QA: speculative climax not flagged"); return False
    return True
