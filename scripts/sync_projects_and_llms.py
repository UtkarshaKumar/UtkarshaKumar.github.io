#!/usr/bin/env python3
"""Write the featured project list and the llms.txt lists as static text.

Runs after sync_writing.py. Featured projects are repos whose GitHub homepage
points at this site. They are written as plain HTML into projects.html (all)
and index.html (newest three), so crawlers see them without running
JavaScript, and as markdown into llms.txt. The llms.txt writing list is read
back from writing.html, so it always matches the published list.

A failed GitHub fetch leaves every project block as it was.
"""

import html as html_lib
import os
import re
import sys

import requests

from sync_writing import ROOT, inject

LLMS = ROOT / "llms.txt"
SITE_URL = "https://utkarshakumar.github.io/"
GITHUB_REPOS_API = "https://api.github.com/users/UtkarshaKumar/repos?type=owner&per_page=100"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HOMEPAGE_PROJECT_COUNT = 3
# Listed first, in this order; the rest follow newest first.
PINNED_PROJECTS = ["shopsense-ai"]

# Product names as the GitHub profile README writes them. Other repos fall back to title case.
DISPLAY_NAMES = {
    "cloudnest": "CloudNest",
    "nudge-pro": "Nudge Pro",
    "pagesmith": "PageSmith",
    "shopsense-ai": "ShopSense AI",
}
LANGUAGE_COLORS = {
    "Swift": "#f05138", "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#563d7c", "Jupyter Notebook": "#DA5B0B", "Rust": "#dea584",
}

WROW_RE = re.compile(
    r'<a class="wrow" href="([^"]+)"[^>]*>'
    r'<span class="wdate">(.*?)</span>'
    r'<span class="wtitle">(.*?)</span>'
)


def without_dashes(text):
    """Site copy rule: no em or en dashes, including in text pulled from GitHub."""
    text = re.sub(r"(?<=\d)\u2013(?=\d)", " to ", text or "")
    return re.sub(r"\s*[\u2014\u2013]\s*", ", ", text).strip()


def md_link(label, url):
    label = without_dashes(label).replace("[", "\\[").replace("]", "\\]")
    return f"[{label}]({url})"


# ── writing (llms.txt only) ─────────────────────────────────────────────

def llms_writing_rows():
    page = (ROOT / "writing.html").read_text(encoding="utf-8")
    block = page.split("<!-- WRITING_LIST_START -->", 1)[-1].split("<!-- WRITING_LIST_END -->", 1)[0]
    rows = []
    for href, date, title in WROW_RE.findall(block):
        href, title = html_lib.unescape(href), html_lib.unescape(title)
        url = href if href.startswith("http") else SITE_URL + href
        row = f"- {md_link(title, url)}"
        rows.append(f"{row}: published {date}" if re.fullmatch(r"\d{4}-\d{2}", date) else row)
    return rows


# ── projects ────────────────────────────────────────────────────────────

def fetch_featured_projects():
    """Pinned repos first, then newest by creation date, so a push to a repo does
    not reorder the lists. Returns None on failure."""
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        resp = requests.get(GITHUB_REPOS_API, headers=headers, timeout=15)
        resp.raise_for_status()
        repos = resp.json()
    except Exception as e:
        print(f"WARNING: GitHub repo fetch failed: {e}")
        return None
    featured = [r for r in repos if "utkarshakumar.github.io" in (r.get("homepage") or "")]
    newest = sorted(featured, key=lambda r: r["created_at"], reverse=True)
    pinned = [r for name in PINNED_PROJECTS for r in newest if r["name"] == name]
    return pinned + [r for r in newest if r["name"] not in PINNED_PROJECTS]


def display_name(repo):
    return DISPLAY_NAMES.get(repo["name"]) or repo["name"].replace("-", " ").title()


def description(repo):
    """GitHub descriptions often open with the product name; the row already shows it."""
    desc = repo.get("description") or ""
    name = re.escape(display_name(repo))
    desc = re.sub(rf"^{name}\s*(?:[\u2014\u2013:,-]\s*)", "", desc, flags=re.IGNORECASE)
    return without_dashes(desc)


def render_project_row(repo):
    lang = repo.get("language")
    lang_html = (
        f'<span class="plang"><span class="lang-dot" style="background:{LANGUAGE_COLORS.get(lang, "#888")}"></span>'
        f"{html_lib.escape(lang)}</span>"
    ) if lang else "<span></span>"
    desc = description(repo) or "No description provided."
    return (
        f'<a href="{html_lib.escape(repo["html_url"])}" target="_blank" rel="noopener" class="prow">'
        f'<span class="pname">{html_lib.escape(display_name(repo))}</span>'
        f'<span class="pdesc">{html_lib.escape(desc)}</span>'
        f"{lang_html}</a>"
    )


def render_llms_project_row(repo):
    row = f"- {md_link(display_name(repo), repo['html_url'])}"
    desc = description(repo)
    return f"{row}: {desc}" if desc else row


def main():
    writing = llms_writing_rows()
    if writing:
        inject(LLMS, "<!-- WRITING_LIST_START -->", "<!-- WRITING_LIST_END -->", "\n".join(writing))
    else:
        print("WARNING: no writing rows parsed from writing.html; llms.txt writing list left unchanged")

    projects = fetch_featured_projects()
    if projects is not None:
        empty = '<div class="wlist-empty">No featured projects at this time.</div>'
        rows = [render_project_row(r) for r in projects]
        inject(ROOT / "projects.html", "<!-- PROJECT_LIST_START -->", "<!-- PROJECT_LIST_END -->",
               "\n".join(rows) or empty)
        inject(ROOT / "index.html", "<!-- LATEST_PROJECTS_START -->", "<!-- LATEST_PROJECTS_END -->",
               "\n".join(rows[:HOMEPAGE_PROJECT_COUNT]) or empty)
        inject(LLMS, "<!-- PROJECT_LIST_START -->", "<!-- PROJECT_LIST_END -->",
               "\n".join(render_llms_project_row(r) for r in projects) or "No featured projects at this time.")

    print(f"Wrote {len(writing)} llms.txt writing row(s) and "
          f"{'no' if projects is None else len(projects)} project row(s)")


if __name__ == "__main__":
    sys.exit(main())
