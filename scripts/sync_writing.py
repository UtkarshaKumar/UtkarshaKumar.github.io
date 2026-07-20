#!/usr/bin/env python3
"""Sync Notion + Medium + local posts into article pages and the writing list.

Fetches published Notion pages, the public Medium RSS feed, and any markdown
files committed directly to posts/, renders each into a standalone static
article page under writing/<slug>.html (so readers never have to leave the
site), and injects a merged, reverse-chronological list into writing.html
and a single "latest" row into index.html.

posts/*.md is the no-Notion-needed publish path: drop a markdown file with a
title/date frontmatter header in posts/, push, and the next sync picks it up
same as a Notion or Medium post.

Every per-item step degrades gracefully: if full-content rendering fails for
a given post (unexpected block type, network hiccup, etc.), that post falls
back to linking to the original Notion/Medium URL instead of breaking the
whole sync.
"""

import html as html_lib
import os
import re
import sys
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from string import Template

import markdown as md_lib
import requests

ROOT = Path(__file__).resolve().parent.parent
WRITING_DIR = ROOT / "writing"
IMG_DIR = WRITING_DIR / "img"
POSTS_DIR = ROOT / "posts"

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
MEDIUM_FEED = "https://medium.com/feed/@utkarshsingh_96177"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

XML_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}


# ── helpers ──────────────────────────────────────────────────────────────

def slugify(title, maxlen=70):
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:maxlen].rstrip("-") or "untitled"


def unique_slug(base, taken):
    slug = base
    n = 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    taken.add(slug)
    return slug


# ── Notion: rich text + block rendering ─────────────────────────────────

def rich_text_to_html(rich_text_arr):
    out = []
    for rt in rich_text_arr or []:
        text = html_lib.escape(rt.get("plain_text", ""))
        if not text:
            continue
        ann = rt.get("annotations", {})
        if ann.get("code"):
            text = f"<code>{text}</code>"
        if ann.get("bold"):
            text = f"<strong>{text}</strong>"
        if ann.get("italic"):
            text = f"<em>{text}</em>"
        if ann.get("strikethrough"):
            text = f"<s>{text}</s>"
        href = rt.get("href")
        if href:
            text = f'<a href="{html_lib.escape(href)}" target="_blank" rel="noopener">{text}</a>'
        out.append(text)
    return "".join(out)


def fetch_block_children(block_id, depth=0):
    """Paginated fetch of a Notion block's children. Capped recursion depth."""
    if depth > 5:
        return []
    blocks = []
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        resp = requests.get(
            f"https://api.notion.com/v1/blocks/{block_id}/children",
            headers=NOTION_HEADERS,
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return blocks


def download_notion_image(url, slug, index):
    """Notion file URLs are temporary signed links — pull them local so
    they don't rot after the ~1hr expiry."""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        ext = {
            "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg",
            "image/gif": "gif", "image/webp": "webp", "image/svg+xml": "svg",
        }.get(ctype.split(";")[0].strip(), "jpg")
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        fname = f"{slug}-{index}.{ext}"
        (IMG_DIR / fname).write_bytes(resp.content)
        return f"img/{fname}"
    except Exception as e:
        print(f"WARNING: image download failed for {slug}: {e}")
        return None


def render_blocks(blocks, slug, img_counter, depth=0):
    parts = []
    i = 0
    n = len(blocks)
    while i < n:
        b = blocks[i]
        t = b.get("type")
        data = b.get(t, {}) or {}
        try:
            if t == "paragraph":
                text = rich_text_to_html(data.get("rich_text"))
                if text:
                    parts.append(f"<p>{text}</p>")
            elif t in ("heading_1", "heading_2", "heading_3"):
                tag = {"heading_1": "h3", "heading_2": "h4", "heading_3": "h5"}[t]
                text = rich_text_to_html(data.get("rich_text"))
                if text:
                    parts.append(f"<{tag}>{text}</{tag}>")
            elif t == "bulleted_list_item":
                items = []
                while i < n and blocks[i].get("type") == "bulleted_list_item":
                    cur = blocks[i]
                    li = rich_text_to_html(cur["bulleted_list_item"].get("rich_text"))
                    child_html = ""
                    if cur.get("has_children"):
                        child_blocks = fetch_block_children(cur["id"], depth + 1)
                        child_html = render_blocks(child_blocks, slug, img_counter, depth + 1)
                    items.append(f"<li>{li}{child_html}</li>")
                    i += 1
                parts.append("<ul>" + "".join(items) + "</ul>")
                continue
            elif t == "numbered_list_item":
                items = []
                while i < n and blocks[i].get("type") == "numbered_list_item":
                    li = rich_text_to_html(blocks[i]["numbered_list_item"].get("rich_text"))
                    items.append(f"<li>{li}</li>")
                    i += 1
                parts.append("<ol>" + "".join(items) + "</ol>")
                continue
            elif t == "quote":
                text = rich_text_to_html(data.get("rich_text"))
                if text:
                    parts.append(f"<blockquote>{text}</blockquote>")
            elif t == "callout":
                text = rich_text_to_html(data.get("rich_text"))
                icon = (data.get("icon") or {}).get("emoji", "")
                parts.append(f'<div class="callout">{icon} {text}</div>')
            elif t == "code":
                text = "".join(r.get("plain_text", "") for r in data.get("rich_text") or [])
                lang = html_lib.escape(data.get("language", ""))
                parts.append(f'<pre><code class="lang-{lang}">{html_lib.escape(text)}</code></pre>')
            elif t == "image":
                src = (data.get("file") or {}).get("url") or (data.get("external") or {}).get("url", "")
                if src:
                    img_counter[0] += 1
                    local = download_notion_image(src, slug, img_counter[0])
                    if local:
                        caption = rich_text_to_html(data.get("caption"))
                        cap_html = f"<figcaption>{caption}</figcaption>" if caption else ""
                        parts.append(f'<figure><img src="{local}" loading="lazy" alt="">{cap_html}</figure>')
            elif t == "divider":
                parts.append("<hr>")
            elif t == "to_do":
                text = rich_text_to_html(data.get("rich_text"))
                checked = "checked" if data.get("checked") else ""
                parts.append(f'<p><input type="checkbox" disabled {checked}> {text}</p>')
            elif t == "toggle":
                text = rich_text_to_html(data.get("rich_text"))
                child_html = ""
                if b.get("has_children"):
                    child_blocks = fetch_block_children(b["id"], depth + 1)
                    child_html = render_blocks(child_blocks, slug, img_counter, depth + 1)
                parts.append(f"<details><summary>{text}</summary>{child_html}</details>")
            elif t == "bookmark":
                url = data.get("url", "")
                if url:
                    safe = html_lib.escape(url)
                    parts.append(f'<p><a href="{safe}" target="_blank" rel="noopener">{safe}</a></p>')
            elif t in ("embed", "video"):
                url = data.get("url", "")
                if url:
                    safe = html_lib.escape(url)
                    parts.append(f'<p><a href="{safe}" target="_blank" rel="noopener">{safe}</a></p>')
            # unsupported block types (tables, columns, files, synced blocks,
            # equations, databases): skip silently rather than fail the page
        except Exception as e:
            print(f"WARNING: failed to render block type {t}: {e}")
        i += 1
    return "".join(parts)


def get_excerpt(page_id, max_chars=140):
    try:
        resp = requests.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=NOTION_HEADERS,
            params={"page_size": 15},
            timeout=20,
        )
        blocks = resp.json().get("results", [])
        TEXT_TYPES = {
            "paragraph", "heading_1", "heading_2", "heading_3",
            "bulleted_list_item", "numbered_list_item", "quote", "callout",
        }
        for block in blocks:
            btype = block.get("type", "")
            if btype in TEXT_TYPES:
                text = "".join(r.get("plain_text", "") for r in block.get(btype, {}).get("rich_text", [])).strip()
                if text:
                    return text
    except Exception:
        pass
    return ""


def fetch_notion_items(taken_slugs):
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        print("WARNING: NOTION_TOKEN/NOTION_DATABASE_ID not set, skipping Notion")
        return []
    try:
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query",
            headers=NOTION_HEADERS,
            json={
                "filter": {"property": "RequestPublishing", "checkbox": {"equals": True}},
                "sorts": [{"property": "PublishedAt", "direction": "descending"}],
            },
            timeout=20,
        )
        data = resp.json()
    except Exception as e:
        print(f"WARNING: Notion query failed: {e}")
        return []

    if "results" not in data:
        print("WARNING: Notion API returned:", data)
        return []

    items = []
    for page in data["results"]:
        props = page["properties"]
        title_prop = props.get("Title", props.get("Name", {}))
        title_arr = title_prop.get("title", [])
        title = title_arr[0]["plain_text"] if title_arr else "Untitled"

        date_obj = props.get("PublishedAt", {}).get("date") or {}
        date_str = date_obj.get("start", "")

        original_url = page.get("url", "#")
        item = {
            "title": title,
            "url": original_url,
            "sort_key": date_str[:10] if date_str else "0000-00-00",
            "date_disp": date_str[:7] if date_str else "",
            "source": "Notion",
            "local_path": None,
        }

        # Full-content render, best-effort. Falls back to external link + excerpt.
        try:
            slug = unique_slug(slugify(title), taken_slugs)
            img_counter = [0]
            blocks = fetch_block_children(page["id"])
            body_html = render_blocks(blocks, slug, img_counter)
            if body_html.strip():
                write_article_page(slug, title, item["date_disp"], "Notion", original_url, body_html)
                item["local_path"] = f"writing/{slug}.html"
            else:
                item["excerpt"] = get_excerpt(page["id"])
        except Exception as e:
            print(f"WARNING: full-content render failed for '{title}': {e}")
            item["excerpt"] = get_excerpt(page["id"])

        items.append(item)
    return items


# ── Medium ───────────────────────────────────────────────────────────────

TRACKING_IMG_RE = re.compile(r'<img[^>]*medium\.com/_/stat[^>]*>')


def clean_medium_html(raw):
    return TRACKING_IMG_RE.sub("", raw or "")


def fetch_medium_items(taken_slugs, limit=20):
    try:
        resp = requests.get(MEDIUM_FEED, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        print(f"WARNING: Medium fetch failed: {e}")
        return []

    items = []
    for entry in root.findall("./channel/item")[:limit]:
        title = (entry.findtext("title") or "").strip()
        link = (entry.findtext("link") or "").strip()
        pub = entry.findtext("pubDate") or ""
        try:
            dt = parsedate_to_datetime(pub)
            sort_key = dt.strftime("%Y-%m-%d")
            date_disp = dt.strftime("%Y-%m")
        except Exception:
            sort_key, date_disp = "0000-00-00", ""

        item = {
            "title": title,
            "url": link,
            "sort_key": sort_key,
            "date_disp": date_disp,
            "source": "Medium",
            "local_path": None,
        }

        try:
            enc = entry.find("content:encoded", XML_NS)
            body_html = clean_medium_html(enc.text if enc is not None else "")
            if body_html.strip():
                slug = unique_slug(slugify(title), taken_slugs)
                write_article_page(slug, title, date_disp, "Medium", link, body_html)
                item["local_path"] = f"writing/{slug}.html"
        except Exception as e:
            print(f"WARNING: Medium render failed for '{title}': {e}")

        items.append(item)
    return items


# ── article page template ───────────────────────────────────────────────

ARTICLE_TEMPLATE = Template("""<!--
  © 2026 Utkarsha Kumar. All rights reserved.
  This source code and design are the original work of Utkarsha Kumar.
  Auto-generated by the writing sync — do not hand-edit, changes will be
  overwritten on the next sync run.
-->
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="$desc">
  <meta property="og:title" content="$title">
  <meta property="og:type" content="article">
  <link rel="icon" type="image/jpeg" href="../profile.jpg">
  <title>$title — Utkarsha Kumar</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../assets/styles.css">
  <style>
    .subpage-hero { background:#0C0B09; color:#EDE8DE; padding:9rem 2rem 2.5rem; border-bottom:1px solid rgba(255,255,255,0.04); }
    .subpage-hero .impact-title { max-width: 780px; }
    .article-meta { font-size:0.8rem; color:rgba(237,232,222,0.4); margin-top:0.9rem; }
    .article-meta a { color:var(--accent); text-decoration:none; font-weight:600; }
    .article-meta a:hover { text-decoration:underline; }
    .article-body { max-width:680px; margin:0 auto; padding:3.5rem 2rem; font-size:1.02rem; line-height:1.85; color:var(--text-2); }
    .article-body h3, .article-body h4, .article-body h5 { font-family:'et-book',Palatino,Georgia,serif; color:var(--text); margin:2rem 0 1rem; line-height:1.3; }
    .article-body p { margin-bottom:1.3rem; }
    .article-body ul, .article-body ol { margin:0 0 1.3rem 1.3rem; }
    .article-body li { margin-bottom:0.5rem; }
    .article-body blockquote { border-left:3px solid var(--accent); padding-left:1.2rem; margin:1.5rem 0; font-style:italic; color:var(--text-2); }
    .article-body img { max-width:100%; height:auto; border-radius:6px; display:block; margin:0 auto; }
    .article-body figure { margin:1.5rem 0; }
    .article-body figcaption { font-size:0.8rem; color:var(--text-3); text-align:center; margin-top:0.5rem; }
    .article-body pre { background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:1rem; overflow-x:auto; margin:1.5rem 0; }
    .article-body code { font-family:'JetBrains Mono',monospace; font-size:0.85em; }
    .article-body hr { border:none; border-top:1px solid var(--border); margin:2.5rem 0; }
    .article-body a { color:var(--accent); }
    .article-body .callout { background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:1rem 1.2rem; margin:1.5rem 0; }
    .article-back { max-width:680px; margin:0 auto; padding:0 2rem 2rem; }
    .article-back a { color:var(--text-3); text-decoration:none; font-size:0.85rem; font-weight:600; }
    .article-back a:hover { color:var(--accent); }
  </style>
</head>

<body>

  <!-- ===== NAV ===== -->
  <nav id="top">
    <div class="nav-inner">
      <div class="nav-brand-group">
        <a href="../index.html" class="nav-brand">Utkarsha Kumar</a>
        <span class="nav-role">Product Leader &middot; Bengaluru, India</span>
      </div>
      <div class="nav-links">
        <a href="../experience.html">Experience</a>
        <a href="../projects.html">Projects</a>
        <a href="../writing.html" class="nav-current">Writing</a>
        <a href="https://github.com/UtkarshaKumar" target="_blank" rel="noopener" class="nav-btn" title="GitHub">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/></svg>
        </a>
        <a href="https://medium.com/@utkarshsingh_96177" target="_blank" rel="noopener" class="nav-btn" title="Medium">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M13.54 12a6.8 6.8 0 0 1-6.77 6.82A6.8 6.8 0 0 1 0 12a6.8 6.8 0 0 1 6.77-6.82A6.8 6.8 0 0 1 13.54 12zM20.96 12c0 3.54-1.51 6.42-3.38 6.42-1.87 0-3.39-2.88-3.39-6.42s1.52-6.42 3.39-6.42 3.38 2.88 3.38 6.42M24 12c0 3.17-.53 5.75-1.19 5.75-.66 0-1.19-2.58-1.19-5.75s.53-5.75 1.19-5.75C23.47 6.25 24 8.83 24 12z"/></svg>
        </a>
        <button class="nav-btn" id="themeToggle" aria-label="Toggle theme">
          <svg class="icon-moon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          <svg class="icon-sun" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        </button>
        <a href="https://linkedin.com/in/utkkumar" target="_blank" rel="noopener" class="nav-btn nav-cta">Connect</a>
      </div>
      <button class="nav-toggle" id="hamburger" aria-label="Toggle navigation" aria-expanded="false">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
          <path class="toggle-line line-top" d="M2,7 L22,7"/>
          <path class="toggle-line line-mid" d="M5,12 L22,12"/>
          <path class="toggle-line line-bot" d="M2,17 L22,17"/>
        </svg>
      </button>
    </div>
    <div id="mobile-menu">
      <div class="mobile-role">Product Leader &middot; Bengaluru, India</div>
      <div class="mobile-theme-row">
        <span>Theme</span>
        <button class="mobile-theme-btn" id="mobileThemeToggle" aria-label="Toggle theme">
          <svg class="icon-moon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          <svg class="icon-sun" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/></svg>
          <span id="mobileThemeLabel">Light</span>
        </button>
      </div>
      <a href="../experience.html">Experience</a>
      <a href="../projects.html">Projects</a>
      <a href="../writing.html">Writing</a>
      <a href="https://linkedin.com/in/utkkumar" target="_blank" rel="noopener" class="m-accent">LinkedIn &#8599;</a>
      <a href="https://github.com/UtkarshaKumar" target="_blank" rel="noopener" class="m-accent">GitHub &#8599;</a>
      <a href="https://medium.com/@utkarshsingh_96177" target="_blank" rel="noopener" class="m-accent">Medium &#8599;</a>
      <a href="mailto:utkarshsinghinbox@gmail.com" class="m-accent">Email</a>
    </div>
  </nav>

  <header class="subpage-hero">
    <div class="container">
      <span class="section-label" style="color:#E07840;">$source</span>
      <h2 class="impact-title">$title</h2>
      <p class="article-meta">$meta_line</p>
    </div>
  </header>

  <article class="article-body">
$body_html
  </article>
  <div class="article-back"><a href="../writing.html">&#8592; Back to Writing</a></div>

  <!-- ===== FOOTER ===== -->
  <footer id="contact">
    <div class="footer-inner">
      <div>
        <p class="footer-name">Utkarsha Kumar</p>
        <p class="footer-role">Senior Product Manager &middot; Deloitte Digital &middot; B2B Commerce &amp; AI</p>
      </div>
      <div class="footer-links">
        <a href="https://linkedin.com/in/utkkumar" target="_blank" rel="noopener" class="footer-link">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>
          LinkedIn
        </a>
        <a href="mailto:utkarshsinghinbox@gmail.com" class="footer-link">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,12 2,6"/></svg>
          Email
        </a>
        <a href="https://github.com/UtkarshaKumar" target="_blank" rel="noopener" class="footer-link">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/></svg>
          GitHub
        </a>
        <a href="https://medium.com/@utkarshsingh_96177" target="_blank" rel="noopener" class="footer-link">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M13.54 12a6.8 6.8 0 0 1-6.77 6.82A6.8 6.8 0 0 1 0 12a6.8 6.8 0 0 1 6.77-6.82A6.8 6.8 0 0 1 13.54 12zM20.96 12c0 3.54-1.51 6.42-3.38 6.42-1.87 0-3.39-2.88-3.39-6.42s1.52-6.42 3.39-6.42 3.38 2.88 3.38 6.42M24 12c0 3.17-.53 5.75-1.19 5.75-.66 0-1.19-2.58-1.19-5.75s.53-5.75 1.19-5.75C23.47 6.25 24 8.83 24 12z"/></svg>
          Medium
        </a>
      </div>
      <p class="footer-copy">&copy; 2026 Utkarsha Kumar &middot; All rights reserved &middot; Cloning or reusing without credit is a copyright violation</p>
    </div>
  </footer>

  <div class="cursor-dot" id="cursorDot"></div>
  <div class="cursor-ring" id="cursorRing"></div>

  <script>
    (function () {
      var html = document.documentElement;
      var label = document.getElementById('mobileThemeLabel');
      function applyTheme(t) {
        if (t === 'light') { html.classList.add('light'); if (label) label.textContent = 'Dark'; }
        else { html.classList.remove('light'); if (label) label.textContent = 'Light'; }
      }
      function toggle() {
        var next = html.classList.contains('light') ? 'dark' : 'light';
        applyTheme(next);
        try { localStorage.setItem('theme', next); } catch (e) {}
      }
      var saved; try { saved = localStorage.getItem('theme'); } catch (e) {}
      var sysLight = window.matchMedia('(prefers-color-scheme: light)').matches;
      applyTheme(saved || (sysLight ? 'light' : 'dark'));
      var btn = document.getElementById('themeToggle');
      var mbtn = document.getElementById('mobileThemeToggle');
      if (btn) btn.addEventListener('click', toggle);
      if (mbtn) mbtn.addEventListener('click', toggle);
      window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function (e) {
        var hasSaved; try { hasSaved = !!localStorage.getItem('theme'); } catch (ex) {}
        if (!hasSaved) applyTheme(e.matches ? 'light' : 'dark');
      });
    })();
    var burger = document.getElementById('hamburger');
    var mMenu = document.getElementById('mobile-menu');
    burger.addEventListener('click', function () {
      var isOpen = burger.classList.toggle('open');
      mMenu.classList.toggle('open');
      burger.setAttribute('aria-expanded', isOpen);
    });
    mMenu.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        burger.classList.remove('open');
        mMenu.classList.remove('open');
      });
    });
    (function () {
      if (!window.matchMedia('(pointer: fine)').matches) return;
      var dot = document.getElementById('cursorDot');
      var ring = document.getElementById('cursorRing');
      if (!dot || !ring) return;
      var mx = -200, my = -200, rx = -200, ry = -200, entered = false;
      document.addEventListener('mousemove', function (e) {
        mx = e.clientX; my = e.clientY;
        dot.style.left = mx + 'px'; dot.style.top = my + 'px';
        if (!entered) { entered = true; rx = mx; ry = my; dot.classList.add('on'); ring.classList.add('on'); }
      });
      document.addEventListener('mouseleave', function () { dot.classList.remove('on'); ring.classList.remove('on'); entered = false; });
      document.addEventListener('mouseover', function (e) {
        var t = e.target.closest('a, button, [role="button"], input, textarea, select');
        if (t) { dot.classList.add('hov'); ring.classList.add('hov'); } else { dot.classList.remove('hov'); ring.classList.remove('hov'); }
      });
      document.addEventListener('mousedown', function () { dot.classList.add('dn'); });
      document.addEventListener('mouseup', function () { dot.classList.remove('dn'); });
      (function animRing() {
        rx += (mx - rx) * 0.12; ry += (my - ry) * 0.12;
        ring.style.left = Math.round(rx * 10) / 10 + 'px';
        ring.style.top = Math.round(ry * 10) / 10 + 'px';
        requestAnimationFrame(animRing);
      })();
    })();
  </script>

</body>
</html>
""")


def write_article_page(slug, title, date_disp, source, original_url, body_html):
    WRITING_DIR.mkdir(parents=True, exist_ok=True)
    desc = re.sub(r"<[^>]+>", "", body_html)[:160].strip()
    safe_date = html_lib.escape(date_disp or "")
    if original_url:
        meta_line = (
            f'{safe_date} &middot; Originally published on '
            f'<a href="{html_lib.escape(original_url)}" target="_blank" rel="noopener">{html_lib.escape(source)} &#8599;</a>'
        ) if safe_date else (
            f'Originally published on <a href="{html_lib.escape(original_url)}" target="_blank" rel="noopener">{html_lib.escape(source)} &#8599;</a>'
        )
    else:
        meta_line = safe_date
    html_out = ARTICLE_TEMPLATE.substitute(
        title=html_lib.escape(title),
        desc=html_lib.escape(desc),
        source=html_lib.escape(source),
        meta_line=meta_line,
        body_html=body_html,
    )
    (WRITING_DIR / f"{slug}.html").write_text(html_out, encoding="utf-8")


# ── local posts (no Notion/Medium needed) ───────────────────────────────

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def parse_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    return meta, m.group(2)


def fetch_local_items(taken_slugs):
    if not POSTS_DIR.exists():
        return []
    items = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        try:
            meta, body_md = parse_frontmatter(md_file.read_text(encoding="utf-8"))
            title = meta.get("title") or md_file.stem.replace("-", " ").title()
            date_str = meta.get("date", "")
            body_html = md_lib.markdown(body_md, extensions=["fenced_code", "tables"])
            if not body_html.strip():
                continue
            slug = unique_slug(slugify(title), taken_slugs)
            write_article_page(slug, title, date_str[:7] if date_str else "", "Site", None, body_html)
            items.append({
                "title": title,
                "url": f"writing/{slug}.html",
                "sort_key": date_str[:10] if date_str else "0000-00-00",
                "date_disp": date_str[:7] if date_str else "",
                "source": "Site",
                "local_path": f"writing/{slug}.html",
            })
        except Exception as e:
            print(f"WARNING: local post render failed for {md_file.name}: {e}")
    return items


# ── list rendering + injection ──────────────────────────────────────────

def render_row(it):
    href = it.get("local_path") or it["url"]
    target = "" if it.get("local_path") else ' target="_blank" rel="noopener"'
    safe_date = html_lib.escape(it["date_disp"] or "—")
    safe_title = html_lib.escape(it["title"])
    safe_source = html_lib.escape(it["source"])
    return (
        f'<a class="wrow" href="{href}"{target}>'
        f'<span class="wdate">{safe_date}</span>'
        f'<span class="wtitle">{safe_title}</span>'
        f'<span class="wsource">{safe_source}</span>'
        f"</a>"
    )


def inject(path, start_marker, end_marker, block):
    content = path.read_text(encoding="utf-8")
    pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
    new_content, count = re.subn(
        pattern, f"{start_marker}\n{block}\n{end_marker}", content, flags=re.DOTALL
    )
    if count == 0:
        print(f"WARNING: markers {start_marker}/{end_marker} not found in {path}")
        return
    path.write_text(new_content, encoding="utf-8")


def main():
    taken_slugs = set()
    notion_items = fetch_notion_items(taken_slugs)
    medium_items = fetch_medium_items(taken_slugs)
    local_items = fetch_local_items(taken_slugs)
    merged = sorted(notion_items + medium_items + local_items, key=lambda x: x["sort_key"], reverse=True)

    if merged:
        full_block = "\n".join(render_row(it) for it in merged)
        latest_block = render_row(merged[0])
    else:
        full_block = latest_block = '<div class="wlist-empty">Nothing published yet.</div>'

    inject(ROOT / "writing.html", "<!-- WRITING_LIST_START -->", "<!-- WRITING_LIST_END -->", full_block)
    inject(ROOT / "index.html", "<!-- LATEST_WRITING_START -->", "<!-- LATEST_WRITING_END -->", latest_block)

    rendered = sum(1 for it in merged if it.get("local_path"))
    print(f"Synced {len(merged)} item(s): {len(notion_items)} Notion, {len(medium_items)} Medium, "
          f"{len(local_items)} local, {rendered} rendered locally")


if __name__ == "__main__":
    sys.exit(main())
