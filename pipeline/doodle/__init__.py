"""Doodle (MS-Paint explainer) pipeline — the Axen / Ink Explainer style.

Flow:
  script -> VO (ElevenLabs) -> transcript w/ timestamps (TurboScribe)
         -> one image prompt per timestamp (Higgsfield / GPT Image 2)
         -> images named by timestamp -> ffmpeg assembly -> finished mp4
"""
