"""Build search-index.json from the pages already on the site.

Runs after sync_writing.py and sync_projects_and_llms.py, so it always
reads what is about to be published. Plain stdlib, no network.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "search-index.json"
BODY_CHARS = 6000


def text(fragment):
    fragment = re.sub(r"(?is)<(script|style|svg|nav|footer)\b.*?</\1>", " ", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def first(pattern, src, default=""):
    m = re.search(pattern, src, re.S | re.I)
    return text(m.group(1)) if m else default


def page(rel, kind, body_pattern, date=""):
    src = (ROOT / rel).read_text(encoding="utf-8")
    title = first(r"<h1[^>]*>(.*?)</h1>", src) or first(r"<title>(.*?)</title>", src)
    desc = first(r'<meta name="description" content="([^"]*)"', src)
    body = first(body_pattern, src) or text(src)
    if not date:
        date = (first(r'"datePublished":\s*"([^"]+)"', src)
                or first(r'class="article-meta">([^<]*)<', src))
    return {"title": title, "type": kind, "date": date, "url": rel,
            "description": desc, "body": body[:BODY_CHARS]}


def projects():
    src = (ROOT / "projects.html").read_text(encoding="utf-8")
    block = re.search(r"<!-- PROJECT_LIST_START -->(.*?)<!-- PROJECT_LIST_END -->", src, re.S)
    out = []
    for href, row in re.findall(r'<a href="([^"]+)"[^>]*class="prow">(.*?)</a>', block.group(1) if block else "", re.S):
        name = first(r'<span class="pname">(.*?)</span>', row)
        desc = first(r'<span class="pdesc">(.*?)</span>', row)
        out.append({"title": name, "type": "Project", "date": "", "url": href,
                    "description": desc, "body": desc})
    return out


def main():
    items = []
    for f in sorted((ROOT / "writing").glob("*.html")):
        items.append(page(f"writing/{f.name}", "Essay", r'<article class="article-body">(.*?)</article>'))
    for f in sorted((ROOT / "case-studies").glob("*.html")):
        items.append(page(f"case-studies/{f.name}", "Guide", r"<body[^>]*>(.*?)</body>"))
    items.append(page("experience.html", "Experience", r"<body[^>]*>(.*?)</body>"))
    items += projects()
    items.sort(key=lambda i: i["date"], reverse=True)
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"search-index.json: {len(items)} entries")


if __name__ == "__main__":
    main()
