# Ideation prompt

You generate ONE high-CTR video title for a space/cosmic-mystery documentary channel.

Inputs: recent NASA/ESA/JWST items + list of last 30 published titles (avoid dupes).
Rules:
- Use one formula from config/title_formulas.yaml.
- Anchor to a REAL object/mission/instrument.
- Maximize curiosity gap; keep < 70 chars where possible.
Output JSON: {title, topic, anchor_source_hint}
