# Handoff

Updated: 2026-07-27 00:26 IST
Status: active

## Goal
Maintain the personal website as a clear authority and writing surface rather than a resume homepage.

## Current state
- Homepage: Writing first, then Projects; nav is Experience → Writing → Projects.
- Homepage teases latest 5 articles; full list on `writing.html`.
- Nav subtitle is location-only: `Bengaluru, India` (removed "Product Leader"). Change is local — not pushed yet.
- Sync template in `scripts/sync_writing.py` matches.

## Next action
Commit and push the nav subtitle change when ready.

## Open items
- Missing Notion publication dates still render as `—`.
- Untracked `writing/img/eval-loop-diagram.svg` from a prior sync may need committing if referenced.

## Key files
- `index.html` and other page shells
- `scripts/sync_writing.py`
- `writing/*.html`

## Verification
- Top nav and mobile menu show name + Bengaluru only, no Product Leader label.
