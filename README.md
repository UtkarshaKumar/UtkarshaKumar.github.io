# utkkumar.github.io

Personal website for Utkarsha Kumar's writing, projects, experience, and product work.

## Current structure

- `index.html` — identity, latest writing (5 teasers), then project teasers
- `experience.html` — resume and career record
- `writing.html` — reverse-chronological writing index
- `projects.html` — projects and prototypes
- `scripts/sync_writing.py` — imports Notion and Medium content and generates local article pages
- `handoff.md` — current state and immediate next action

The hourly `writing_sync.yml` workflow updates writing pages. Individual import failures fall back to the original source URL instead of failing the full build. Homepage shows the latest 5 posts; the full list lives on `writing.html`.

Keep inspiration references out of production comments and commit messages. Reuse requires attribution to the original author and repository.
