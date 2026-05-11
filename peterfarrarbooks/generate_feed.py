#!/usr/bin/env python3
"""
Scans all HTML files in the blog/ directory and:
1. Rebuilds feed.xml
2. Rebuilds blog/index.html (newest post featured, next 3 in grid)
Reads: og:title, og:description, og:image, article:published_time,
       article:section, link[rel=canonical]
"""

import os
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

BLOG_DIR = Path("blog")
FEED_FILE = Path("feed.xml")
BLOG_INDEX = Path("blog/index.html")
SITE_URL = "https://www.peterfarrarbooks.com"
MAX_FEED_ITEMS = 20

def get_meta(content, prop):
    patterns = [
        rf'<meta\s+property=["\x27]{re.escape(prop)}["\x27]\s+content=["\x27]([^"\']+)["\x27]',
        rf'<meta\s+content=["\x27]([^"\']+)["\x27]\s+property=["\x27]{re.escape(prop)}["\x27]',
        rf'<meta\s+name=["\x27]{re.escape(prop)}["\x27]\s+content=["\x27]([^"\']+)["\x27]',
        rf'<meta\s+content=["\x27]([^"\']+)["\x27]\s+name=["\x27]{re.escape(prop)}["\x27]',
    ]
    for p in patterns:
        m = re.search(p, content, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""

def get_canonical(content):
    m = re.search(r'<link\s+rel=["\x27]canonical["\x27]\s+href=["\x27]([^"\']+)["\x27]', content, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""

def parse_date(date_str):
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc, hour=9)
        except ValueError:
            continue
    return None

def escape_xml(text):
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;"))

def format_month_year(dt):
    return dt.strftime("%B %Y")

def category_label(section):
    mapping = {
        "leadership": "Leadership &amp; Culture",
        "photography": "Photography",
        "photography and business": "Photography &amp; Business",
    }
    return mapping.get(section.lower(), section)

def category_filter(section):
    s = section.lower()
    if "leadership" in s:
        return "leadership"
    if "photography" in s:
        return "photography"
    return "all"

def clean_title(title):
    return re.sub(r'\s*\|\s*Peter Farrar Books\s*$', '', title).strip()

# ── Collect posts ──────────────────────────────────────────────
posts = []

for html_file in list(BLOG_DIR.rglob("*.html")) + [f for f in BLOG_DIR.rglob("*") if f.is_file() and f.suffix == "" and f.name != "index"]:
    if html_file.name == "index.html":
        continue
    content = html_file.read_text(encoding="utf-8", errors="ignore")

    title   = clean_title(get_meta(content, "og:title"))
    desc    = get_meta(content, "og:description")
    image   = get_meta(content, "og:image")
    date_s  = get_meta(content, "article:published_time")
    section = get_meta(content, "article:section")
    url     = get_canonical(content)

    if not title or not date_s or not url:
        print(f"  Skipping {html_file} — missing title, date, or URL", file=sys.stderr)
        continue

    dt = parse_date(date_s)
    if not dt:
        print(f"  Skipping {html_file} — bad date: {date_s}", file=sys.stderr)
        continue

    # Derive relative URL path from canonical
    rel_url = url.replace(SITE_URL, "")

    posts.append({
        "title":   title,
        "url":     url,
        "rel_url": rel_url,
        "desc":    desc,
        "image":   image,
        "date":    dt,
        "section": section,
    })

posts.sort(key=lambda p: p["date"], reverse=True)

# ── 1. Rebuild feed.xml ────────────────────────────────────────
items_xml = ""
for p in posts[:MAX_FEED_ITEMS]:
    pub_date  = format_datetime(p["date"])
    enclosure = f'\n      <enclosure url="{escape_xml(p["image"])}" length="0" type="image/jpeg"/>' if p["image"] else ""
    items_xml += f"""
    <item>
      <title><![CDATA[{p["title"]}]]></title>
      <link>{escape_xml(p["url"])}</link>
      <guid>{escape_xml(p["url"])}</guid>
      <pubDate>{pub_date}</pubDate>
      <description><![CDATA[{p["desc"]}]]></description>
      <category>{escape_xml(p["section"])}</category>{enclosure}
    </item>"""

feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Peter Farrar Books — Blog</title>
    <link>https://www.peterfarrarbooks.com/blog/</link>
    <description>Photography insights, leadership thinking, and updates on new books and projects.</description>
    <language>en-gb</language>
    <atom:link href="https://www.peterfarrarbooks.com/feed.xml" rel="self" type="application/rss+xml"/>{items_xml}
  </channel>
</rss>"""

FEED_FILE.write_text(feed, encoding="utf-8")
print(f"feed.xml written with {len(posts[:MAX_FEED_ITEMS])} posts.")

# ── 2. Rebuild blog/index.html ─────────────────────────────────
if not posts:
    print("No posts found — skipping blog/index.html", file=sys.stderr)
    sys.exit(0)

featured = posts[0]
grid_posts = posts[1:4]  # next 3

def featured_card(p):
    cat_label  = category_label(p["section"])
    cat_filter = category_filter(p["section"])
    month_year = format_month_year(p["date"])
    return f"""      <article class="post-featured" data-category="{cat_filter}">
        <div class="post-featured__img">
          <img src="{p["image"]}" alt="{p["title"]}" loading="eager">
        </div>
        <div class="post-featured__body">
          <span class="post-tag">{cat_label}</span>
          <span class="post-meta">{month_year}</span>
          <h2 class="post-title">
            <a href="{p["rel_url"]}">{p["title"]}</a>
          </h2>
          <p class="post-excerpt">{p["desc"]}</p>
          <a href="{p["rel_url"]}" class="post-readmore">Read Post</a>
        </div>
      </article>"""

def grid_card(p):
    cat_label  = category_label(p["section"])
    cat_filter = category_filter(p["section"])
    month_year = format_month_year(p["date"])
    return f"""        <article class="post-card" data-category="{cat_filter}">
          <div class="post-card__img">
            <img src="{p["image"]}" alt="{p["title"]}" loading="lazy">
          </div>
          <div class="post-card__body">
            <span class="post-tag">{cat_label}</span>
            <span class="post-meta">{month_year}</span>
            <h3 class="post-title">
              <a href="{p["rel_url"]}">{p["title"]}</a>
            </h3>
            <p class="post-excerpt">{p["desc"]}</p>
            <a href="{p["rel_url"]}" class="post-readmore">Read Post</a>
          </div>
        </article>"""

grid_html = "\n".join(grid_card(p) for p in grid_posts)

blog_index = f"""<!DOCTYPE html>
<html lang="en">
<head>
<link rel="alternate" type="application/rss+xml" title="Peter Farrar Books Blog" href="https://www.peterfarrarbooks.com/feed.xml">
<link rel="apple-touch-icon" sizes="180x180" href="/images/appletouch.png">
<link rel="icon" type="image/png" href="/images/appletouch.png">

<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="Photography techniques and leadership insights from Peter Farrar — author of The Complete Photography Field Guide and Leadership: The Culture Fix.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://www.peterfarrarbooks.com/blog" />
<title>Photography &amp; Leadership Blog | Peter Farrar Books</title>

<meta property="og:title" content="Photography &amp; Leadership Blog | Peter Farrar Books">
<meta property="og:description" content="Photography techniques and leadership insights from Peter Farrar — author of The Complete Photography Field Guide and Leadership: The Culture Fix.">
<meta property="og:image" content="https://www.peterfarrarbooks.com/images/author.jpg">
<meta property="og:url" content="https://www.peterfarrarbooks.com/blog">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Peter Farrar Books">

<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@graph": [
    {{
      "@type": "WebSite",
      "@id": "https://www.peterfarrarbooks.com/#website",
      "url": "https://www.peterfarrarbooks.com/",
      "name": "Peter Farrar Books",
      "description": "Leadership and photography books by Peter Farrar",
      "publisher": {{ "@id": "https://www.peterfarrarbooks.com/#person" }}
    }},
    {{
      "@type": "Person",
      "@id": "https://www.peterfarrarbooks.com/#person",
      "name": "Peter Farrar",
      "url": "https://www.peterfarrarbooks.com/about",
      "jobTitle": "Author, Photographer and Leadership Expert",
      "description": "Author of leadership and photography books with 30+ years experience",
      "sameAs": [
        "https://www.linkedin.com/in/pfarrar/",
        "https://www.instagram.com/kennethlightstudios/",
        "https://www.facebook.com/KennethLightStudios/",
        "https://x.com/Kennethstudios/"
      ]
    }}
  ]
}}
</script>

<script async src="https://www.googletagmanager.com/gtag/js?id=G-XW133STPV9"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-XW133STPV9');
</script>

<link rel="stylesheet" href="/css/styles.css">

<style>
.blog-filters {{
  display: flex; gap: 8px; flex-wrap: wrap; margin-top: 28px;
}}
.filter-btn {{
  font-family: var(--font-sans); font-size: 0.72rem; font-weight: 600;
  letter-spacing: 0.12em; text-transform: uppercase;
  padding: 7px 18px; background: transparent;
  border: 1px solid var(--border-mid); color: var(--text-muted);
  cursor: pointer; border-radius: var(--radius); transition: all var(--transition);
}}
.filter-btn:hover, .filter-btn.active {{
  border-color: var(--gold); color: var(--gold); background: rgba(196,149,61,0.06);
}}
.post-featured {{
  display: grid; grid-template-columns: 1fr 1fr;
  border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden; background: var(--bg-card); box-shadow: var(--shadow);
  margin-bottom: 12px; transition: box-shadow var(--transition), border-color var(--transition);
}}
.post-featured:hover {{ box-shadow: var(--shadow-lg); border-color: var(--gold-dim); }}
.post-featured__img {{ aspect-ratio: 4/3; overflow: hidden; }}
.post-featured__img img {{
  width: 100%; height: 100%; object-fit: cover; display: block;
  transition: transform 0.4s ease;
}}
.post-featured:hover .post-featured__img img {{ transform: scale(1.03); }}
.post-featured__body {{
  padding: 44px 40px; display: flex; flex-direction: column;
  justify-content: center; border-left: 1px solid var(--border);
}}
.post-tag {{
  font-family: var(--font-sans); font-size: 0.7rem; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--gold); margin-bottom: 10px; display: block;
}}
.post-meta {{
  font-family: var(--font-sans); font-size: 0.72rem; font-weight: 300;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--text-muted); margin-bottom: 14px; display: block;
}}
.post-title {{
  font-family: var(--font-serif); font-weight: normal;
  color: var(--text); line-height: 1.25; margin: 0 0 14px;
}}
.post-title a {{ color: inherit; text-decoration: none; transition: color var(--transition); }}
.post-title a:hover {{ color: var(--gold); }}
.post-featured__body .post-title {{ font-size: clamp(1.1rem, 1.8vw, 1.45rem); }}
.post-excerpt {{
  font-family: var(--font-serif); font-size: 0.95rem;
  color: var(--text-muted); line-height: 1.75; margin: 0 0 24px;
}}
.post-readmore {{
  font-family: var(--font-sans); font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--gold); text-decoration: none;
  display: inline-flex; align-items: center; gap: 6px;
  transition: gap var(--transition); margin-top: auto;
}}
.post-readmore::after {{ content: '→'; }}
.post-readmore:hover {{ color: var(--gold-light); gap: 10px; }}
.blog-divider {{
  display: flex; align-items: center; gap: 20px; margin: 36px 0;
}}
.blog-divider::before, .blog-divider::after {{
  content: ''; flex: 1; height: 1px; background: var(--border);
}}
.blog-divider span {{
  font-family: var(--font-sans); font-size: 0.68rem; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--text-muted); white-space: nowrap;
}}
.post-grid {{
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;
}}
.post-card {{
  border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden; background: var(--bg-card); box-shadow: var(--shadow);
  display: flex; flex-direction: column;
  transition: box-shadow var(--transition), transform var(--transition), border-color var(--transition);
}}
.post-card:hover {{
  box-shadow: var(--shadow-lg); transform: translateY(-3px); border-color: var(--gold-dim);
}}
.post-card__img {{ aspect-ratio: 16/9; overflow: hidden; flex-shrink: 0; }}
.post-card__img img {{
  width: 100%; height: 100%; object-fit: cover; display: block;
  transition: transform 0.4s ease;
}}
.post-card:hover .post-card__img img {{ transform: scale(1.04); }}
.post-card__body {{
  padding: 22px 22px 26px; display: flex; flex-direction: column; flex: 1;
}}
.post-card__body .post-title {{ font-size: 1rem; flex: 1; margin-bottom: 16px; }}
.post-card__body .post-excerpt {{
  font-size: 0.88rem; margin-bottom: 18px;
  display: -webkit-box; -webkit-line-clamp: 3;
  -webkit-box-orient: vertical; overflow: hidden;
}}
@media (max-width: 900px) {{
  .post-featured {{ grid-template-columns: 1fr; }}
  .post-featured__img {{ aspect-ratio: 16/9; }}
  .post-featured__body {{ border-left: none; border-top: 1px solid var(--border); padding: 28px; }}
  .post-grid {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 600px) {{
  .post-grid {{ grid-template-columns: 1fr; }}
}}
</style>

</head>
<body>

<header class="site-header">
  <div class="container header-inner">
    <div class="logo">
      <a href="/">
        <span class="logo-name">Peter Farrar</span>
        <span class="logo-sub">Books</span>
      </a>
    </div>
    <button class="nav-toggle" aria-label="Toggle navigation">&#9776;</button>
    <nav class="site-nav" aria-label="Main navigation">
      <ul>
        <li><a href="/">Home</a></li>
        <li><a href="/books">Books</a></li>
        <li><a href="/coming-soon">Coming 2026</a></li>
        <li><a href="/blog" class="active">Blog</a></li>
        <li><a href="/coaching">Coaching</a></li>
        <li><a href="/about">About</a></li>
        <li><a href="/contact">Contact</a></li>
      </ul>
    </nav>
  </div>
</header>

<main>

  <div class="page-hero" style="text-align:left; padding-bottom:0;">
    <div class="container">
      <p class="breadcrumb">Home / Blog</p>
      <h1>The <em>Blog</em></h1>
      <p style="margin:0;">Photography insights, leadership thinking, and updates on new books and projects.</p>
      <div class="blog-filters">
        <button class="filter-btn active" data-filter="all">All Posts</button>
        <button class="filter-btn" data-filter="leadership">Leadership</button>
        <button class="filter-btn" data-filter="photography">Photography</button>
      </div>
    </div>
  </div>

  <section class="blog-section">
    <div class="container">

{featured_card(featured)}

      <div class="blog-divider"><span>More Posts</span></div>

      <div class="post-grid">
{grid_html}
      </div>

    </div>
  </section>

</main>

<footer class="site-footer">
  <div class="container footer-inner">
    <div class="footer-brand">
      <span class="logo-name">Peter Farrar</span>
      <span class="logo-sub">Books</span>
      <p>Author · Photographer · Leadership Expert</p>
    </div>
    <div class="footer-nav">
      <p class="footer-heading">Pages</p>
      <ul>
        <li><a href="/">Home</a></li>
        <li><a href="/books">Published Books</a></li>
        <li><a href="/coming-soon">Coming 2026</a></li>
        <li><a href="/blog">Blog</a></li>
        <li><a href="/coaching">Coaching</a></li>
        <li><a href="/about">About Peter</a></li>
        <li><a href="/contact">Contact</a></li>
        <li><a href="/privacy">Privacy Policy</a></li>
      </ul>
    </div>
    <div class="footer-nav">
      <p class="footer-heading">Books</p>
      <ul>
        <li><a href="/books#series">Photography Series</a></li>
        <li><a href="/books#field-guide">Complete Field Guide</a></li>
        <li><a href="/books#leadership">Leadership: The Culture Fix</a></li>
        <li><a href="/coming-soon">Coming Soon</a></li>
      </ul>
    </div>
    <div class="footer-social">
      <p class="footer-heading">Connect</p>
      <ul>
        <li><a href="https://www.facebook.com/KennethLightStudios/" target="_blank" rel="noopener">Facebook</a></li>
        <li><a href="https://www.instagram.com/kennethlightstudios/" target="_blank" rel="noopener">Instagram</a></li>
        <li><a href="https://www.linkedin.com/in/pfarrar/" target="_blank" rel="noopener">LinkedIn</a></li>
        <li><a href="https://x.com/Kennethstudios/" target="_blank" rel="noopener">X (Twitter)</a></li>
      </ul>
    </div>
  </div>
  <div class="footer-bottom">
    <div class="container">
      <p>&copy; Peter Farrar. All Rights Reserved. | <a href="/privacy">Privacy Policy</a></p>
    </div>
  </div>
</footer>

<script src="/js/main.js"></script>
<script>
  const btns = document.querySelectorAll('.filter-btn');
  const featured = document.querySelector('.post-featured');
  const cards = document.querySelectorAll('.post-card');
  const divider = document.querySelector('.blog-divider');

  btns.forEach(btn => {{
    btn.addEventListener('click', () => {{
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const f = btn.dataset.filter;
      const showFeatured = f === 'all' || featured.dataset.category === f;
      featured.style.display = showFeatured ? '' : 'none';
      divider.style.display = showFeatured ? '' : 'none';
      cards.forEach(card => {{
        card.style.display = (f === 'all' || card.dataset.category === f) ? '' : 'none';
      }});
    }});
  }});
</script>

</body>
</html>"""

BLOG_INDEX.write_text(blog_index, encoding="utf-8")
print(f"blog/index.html written — featured: '{featured['title']}', grid: {len(grid_posts)} posts.")
