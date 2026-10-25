# utkkumar.github.io

Personal website for Utkarsha Kumar's writing, projects, experience, and product work.

## Current structure

- `index.html`: identity, latest writing (5 teasers), then project teasers
- `experience.html`: resume and career record
- `writing.html`: reverse-chronological writing index
- `projects.html`: projects and prototypes, written as static HTML so crawlers see them
- `llms.txt`: summary for AI assistants ([llmstxt.org](https://llmstxt.org/) format). The summary at the top is hand-written: update it when `experience.html` changes.
- `scripts/sync_projects_and_llms.py`: runs after the writing sync. Writes featured GitHub repos (homepage set to this site; `PINNED_PROJECTS` first) into `projects.html`, the homepage, and `llms.txt`, and copies the writing list into `llms.txt`
- `scripts/sync_writing.py`: imports Notion and Medium content and generates local article pages
- `handoff.md`: current state and immediate next action

The hourly `writing_sync.yml` workflow updates writing pages. Individual import failures fall back to the original source URL instead of failing the full build. Homepage shows the latest 5 posts; the full list lives on `writing.html`.

Keep inspiration references out of production comments and commit messages. Reuse requires attribution to the original author and repository.
