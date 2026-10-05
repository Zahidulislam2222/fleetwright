# Media manifest

Generated through OpenRouter with `tools/media/generate.py` (model IDs in `tools/media/config.json`,
prompts in `tools/media/prompts.json`). Raw job records: `design/media/jobs/*.json`. Originals are
kept locally in `design/media/originals/` (gitignored, large).

| id | Purpose | Source | Factual status | Delivery files | Cost (reported) |
|---|---|---|---|---|---|
| hero-still | Image-to-video first frame | `openai/gpt-image-2.5-sunburst`, 16:9, quality high, 2026-10-05 | Illustrative metaphor (fleet → beacon); not a product capture | — (superseded by the video's first frame as poster) | $0.03332 |
| hero-video | Hero background loop | `bytedance/seedance-2.5`, image-to-video from hero-still, 8 s, 720p, 16:9, no audio, 2026-10-05 | Illustrative | `public/media/hero-fleet.mp4` (1280×720, 7.04 s seamless loop, 1.37 MB); `public/media/hero-fleet-mobile.mp4` (540×962 centre crop, 0.48 MB); `public/media/hero-poster.webp` (first displayed frame of the loop) | $1.85859 |

Total paid generation so far: **$1.89**.

## Processing

- Loop: the clip's last second is crossfaded into its first second (`xfade` 1 s), so the final frame is
  the loop's first frame. Measured seam difference: mean 2.0/255 between first and last frame.
- Encode: H.264 High, CRF 23 (desktop) / 25 (mobile), GOP 48, `+faststart`, audio stripped.
- Poster: first frame of the delivered loop, so the poster-to-video handoff does not jump.

## Review notes

- Reviewed frames 0, 48, 96, 144, 190 of the original: no cuts, no new objects, sky stays black,
  steady forward glide. Vessels read as small lit houseboats; acceptable for the metaphor.
- Rights: generated for this project through the account holder's OpenRouter key; check each
  provider's current output terms before commercial use.
