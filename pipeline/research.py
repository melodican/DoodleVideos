"""[2] RESEARCH — the GROUNDING step that keeps the channel monetizable.

Returns verifiable facts with citations for the chosen topic. Offline-first:
pulls from the curated seed library. Live augmentation (NASA/ESA APIs, web
search) is optional and must append facts in the same {claim, source_name,
source_url} shape so the QA gate can verify coverage.
"""
from __future__ import annotations
import pathlib
import yaml

_TOPICS = pathlib.Path(__file__).parent.parent / "config" / "seed_topics.yaml"


def gather(topic: dict) -> list[dict]:
    """Return [{claim, source_name, source_url}] for the topic."""
    facts = list(topic.get("facts", []))
    # If called with a thin topic (e.g. id only), hydrate from the library.
    if not facts and topic.get("id"):
        lib = {t["id"]: t for t in yaml.safe_load(_TOPICS.read_text())["topics"]}
        facts = lib.get(topic["id"], {}).get("facts", [])
    facts += _live_augment(topic)
    if not facts:
        raise RuntimeError(f"No grounded facts for topic {topic.get('id')!r}")
    return facts


def _live_augment(topic: dict) -> list[dict]:
    """Optionally fetch fresh facts from NASA/ESA. No-op if network/keys absent."""
    # TODO: query NASA APIs / web search; return extra {claim, source_*} dicts.
    return []
