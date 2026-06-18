"""[1] IDEATE — mine recent space topics and generate a curiosity-gap title.

Strategy:
  - Pull recent NASA/ESA/JWST press items + evergreen mystery topics.
  - Fill a proven formula from config/title_formulas.yaml.
  - Score candidates for curiosity gap + novelty; avoid recent duplicates.
"""
from __future__ import annotations
import yaml, pathlib

_CFG = pathlib.Path(__file__).parent.parent / "config" / "title_formulas.yaml"


def load_formulas() -> dict:
    return yaml.safe_load(_CFG.read_text())


def pick_topic() -> tuple[dict, str]:
    """Return (topic_dict, title). TODO: wire to NASA feed + LLM scorer."""
    # TODO: fetch recent missions/press; rank by curiosity-gap with LLM.
    raise NotImplementedError("Wire NASA/ESA feed + LLM title scorer here.")
