"""[6] THUMBNAIL — produce concept specs (offline) and/or images (with a gen key).

Offline it returns two A/B concept briefs the editor/image-gen step can render.
"""
from __future__ import annotations


def make(title: str, topic: dict | None = None) -> list[dict]:
    subject = (topic or {}).get("thumbnail_subject", "dramatic cosmic object")
    caption_a = "IT'S HORRIFYING" if "horrif" in title.lower() else "WHAT THEY FOUND"
    return [
        {"variant": "A", "subject": subject, "caption": caption_a,
         "style": "high-contrast, glow, single focal object, bold sans caption"},
        {"variant": "B", "subject": subject, "caption": "IMPOSSIBLE?",
         "style": "dark background, dramatic rim light, arrow to anomaly"},
    ]
    # TODO: if IMAGE_GEN key present, render PNGs and return file paths instead.
