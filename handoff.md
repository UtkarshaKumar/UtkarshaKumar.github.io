# Handoff

Updated: 2026-07-27 00:15 IST
Status: active

## Goal
Maintain the personal website as a clear authority and writing surface rather than a resume homepage.

## Current state
- Homepage section order is Writing first, then Projects & Prototypes.
- Nav order across pages is Experience → Writing → Projects.
- Homepage teases the latest 5 articles (`HOMEPAGE_LATEST_COUNT` in `scripts/sync_writing.py`); full list on `writing.html` (7 posts including local `posts/the-loop-was-never-about-checkout.md`).
- Local sync without Notion credentials drops Notion rows from the injected lists — CI with secrets remains the full merge path. Notion article HTML files are still present under `writing/`.

## Next action
Push these HTML/nav/sync changes, then confirm the next hourly `writing_sync.yml` run re-merges Notion + Medium + local without shrinking the list.

## Open items
- Notion remains the authoring tool by choice.
- Missing Notion publication dates currently render as `—`.
- Fill missing `PublishedAt` values for the four Notion posts.

## Key files
- `index.html`
- `writing.html`
- `scripts/sync_writing.py`
- `.github/workflows/writing_sync.yml`
- `projects.html`

## Verification
- Homepage: writing section appears before projects; 5 article rows visible.
- Writing page: 7 article rows.
- After CI sync: list still includes Notion posts.
