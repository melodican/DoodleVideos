"""[BROLL] CHANNEL BLUEPRINT — per-channel/format render options.

Captions, motion, source, pacing are *channel-level* choices, not universal
defaults. A long-form documentary (e.g. Rise & Ruin) wants a clean frame with NO
burned captions; a short explainer may want them on. Those choices live in a
channel blueprint (config/channels/<name>.yaml), loaded into RenderOptions.

The default RenderOptions deliberately has captions OFF — nothing forces captions
into the render path.
"""
from __future__ import annotations
import pathlib
from dataclasses import dataclass, asdict

_ROOT = pathlib.Path(__file__).parent.parent.parent
_CHANNELS = _ROOT / "config" / "channels"


@dataclass
class RenderOptions:
    source: str = "stock"            # stock (Pexels) | images (on-hand AI images)
    captions: str = "off"            # off | on  — NOT forced on by default
    caption_style: str = "bold"      # bold | minimal | lower (see captions.STYLES)
    motion: bool = False             # Ken Burns on stills (perf-heavy)
    seconds_per_clip: float | None = None

    @property
    def captions_on(self) -> bool:
        return str(self.captions).lower() in ("on", "true", "1", "yes")


def render_options_from_dict(d: dict) -> RenderOptions:
    """Build RenderOptions from a `render:` mapping (unknown keys ignored)."""
    d = d or {}
    fields = {f for f in RenderOptions().__dict__}
    return RenderOptions(**{k: v for k, v in d.items() if k in fields})


def load_channel(name_or_path: str) -> RenderOptions:
    """Load a channel blueprint's render options by name (config/channels/<name>.yaml)
    or an explicit path. Raises FileNotFoundError if it doesn't exist."""
    import yaml
    p = pathlib.Path(name_or_path)
    if not p.exists():
        p = _CHANNELS / f"{name_or_path}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"channel blueprint not found: {name_or_path}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return render_options_from_dict(data.get("render", {}))


def to_dict(opts: RenderOptions) -> dict:
    return asdict(opts)
