# Social preview

GitHub social preview: 1280×640px, <1 MB, PNG/JPG.

Upload at: **GitHub → Settings → General → Social preview → Edit**

Source file for this repo: `docs/assets/social-preview.svg` (1280×640, vector master).
Exported PNG: `docs/assets/social-preview.png` (generated via `python scripts/export_preview.py` or any SVG→PNG tool).

Design spec (v0.1):
- Background: #0a0a0a (fiducial dark)
- Title: `fiducial` 96pt mono, #e8e8e8
- Tagline: `AI agents hallucinate pinouts. fiducial catches them.` 24pt
- Sub: `lint → erc → check-intent` 18pt, #9a9a9a
- Badge: CI green dot + `KiCad 10` pill

For now this folder contains the SVG master; run `rsvg-convert` or open in Figma and export 1280×640 PNG, then upload via UI (GitHub does not auto-pull `docs/assets/` — manual upload required).

See ROADMAP.md:24 Social preview image + CITATION.cff
