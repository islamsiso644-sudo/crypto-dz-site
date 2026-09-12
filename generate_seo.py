#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_seo.py — مولّد ملفات SEO الأوتوماتيكية لموقع كريبتو جزائر

ينشئ ويحدّث:
  1) sitemap.xml   — خريطة الموقع لكل الصفحات (مع lastmod من تاريخ git)
  2) robots.txt    — قواعد الفهرسة + رابط الخريطة
  3) feed.xml      — تغذية RSS عربية بالمقالات
  4) حقن وسوم <head> (canonical + og:url + og:image + og:locale + رابط RSS)
  5) حقن بيانات JSON-LD المنظمة (WebSite / Article) — لنتائج جوجل المنسّقة
  6) حقن شريط المشاركة (واتساب/فيسبوك/X/تيليجرام/نسخ الرابط) في المقالات
  7) إضافة CSS لشريط المشاركة في style.css

كل الحقن idempotent بين علامات ثابتة — التكرار لا يكرر شيئًا.
الاستخدام:  python3 generate_seo.py          (توليد + حقن)
            python3 generate_seo.py --clean  (إزالة كل الحقن)
"""

import html as html_mod
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = "https://islamsiso644-sudo.github.io/crypto-dz-site"
OG_IMAGE = f"{SITE}/assets/og-image.jpg"
NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------- علامات الحقن
HEAD_START = "<!-- SEO_HEAD_START -->"
HEAD_END = "<!-- SEO_HEAD_END -->"
SHARE_START = "<!-- SHARE_BAR_START -->"
SHARE_END = "<!-- SHARE_BAR_END -->"
CSS_START = "/* SHARE_CSS_START */"
CSS_END = "/* SHARE_CSS_END */"

ROOT_PAGES = ["index.html", "articles.html", "about.html", "contact.html", "privacy.html"]
ARTICLE_PAGES = sorted(p.name for p in (ROOT / "articles").glob("*.html"))

PRICE_REPORT = "price-report.html"  # يتحدّث يوميًا


# ---------------------------------------------------------------- أدوات مساعدة
def git_date(path: Path, last: bool = True) -> str | None:
    """تاريخ آخر/أول commit للملف بصيغة ISO، أو None عند الفشل."""
    fmt = "%cI" if last else "%cI"
    flag = "-1" if last else "--reverse"
    try:
        out = subprocess.run(
            ["git", "log", flag, f"--format={fmt}", "--", str(path.relative_to(ROOT))],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        line = out.stdout.strip().splitlines()
        return line[0][:10] if line else None
    except Exception:
        return None


def page_url(rel: str) -> str:
    return SITE + "/" if rel == "index.html" else f"{SITE}/{rel}"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> bool:
    p = ROOT / rel
    old = p.read_text(encoding="utf-8") if p.exists() else None
    if old == text:
        return False
    p.write_text(text, encoding="utf-8")
    return True


def extract(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def between_replace(text: str, start: str, end: str, block: str) -> str:
    """استبدال محتوى بين علامتين (أو إدراجه قبل نقطة الإدراج إن لم يوجد)."""
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if pattern.search(text):
        return pattern.sub(start + "\n" + block + "\n" + end, text, count=1)
    return None


# ---------------------------------------------------------------- الصفحات
def collect_pages():
    pages = []
    for rel in ROOT_PAGES:
        pages.append(("root", rel))
    for name in ARTICLE_PAGES:
        pages.append(("article", f"articles/{name}"))
    return pages


def page_meta(rel: str):
    text = read(rel)
    title = extract(r"<title>(.*?)</title>", text)
    desc = extract(r'<meta\s+name="description"\s+content="([^"]*)"', text)
    if not desc:
        desc = extract(r'<meta\s+name="description"\s+content=\'([^\']*)', text)
    lastmod = git_date(ROOT / rel) or NOW.strftime("%Y-%m-%d")
    return {"rel": rel, "url": page_url(rel), "title": title, "desc": desc, "lastmod": lastmod}


# ---------------------------------------------------------------- sitemap / robots / feed
def build_sitemap(metas):
    urls = []
    for m in metas:
        if m["rel"] == "index.html":
            pri, freq = "1.0", "daily"
        elif m["rel"] == f"articles/{PRICE_REPORT}":
            pri, freq = "0.9", "daily"
        elif m["rel"] == "articles.html":
            pri, freq = "0.8", "weekly"
        elif m["rel"].startswith("articles/"):
            pri, freq = "0.7", "weekly"
        else:
            pri, freq = "0.5", "monthly"
        urls.append(
            "  <url>\n"
            f"    <loc>{m['url']}</loc>\n"
            f"    <lastmod>{m['lastmod']}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{pri}</priority>\n"
            "  </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n</urlset>\n"
    )


def build_robots():
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {SITE}/sitemap.xml\n"
    )


def build_feed(metas):
    def item(m, is_report=False):
        pub = NOW.strftime("%a, %d %b %Y %H:%M:%S +0000") if is_report else m["lastmod"]
        return (
            "    <item>\n"
            f"      <title>{html_mod.escape(m['title'])}</title>\n"
            f"      <link>{m['url']}</link>\n"
            f"      <guid isPermaLink=\"true\">{m['url']}</guid>\n"
            f"      <description>{html_mod.escape(m['desc'] or m['title'])}</description>\n"
            f"      <pubDate>{pub}</pubDate>\n"
            "    </item>"
        )
    items = [item(m, is_report=(m["rel"] == f"articles/{PRICE_REPORT}"))
             for m in metas if m["rel"].startswith("articles/")]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>كريبتو جزائر — دليل الكريبتو والدفع الإلكتروني</title>\n"
        f"    <link>{SITE}</link>\n"
        "    <description>أسعار الكريبتو بالدينار يوميًا + أدلة عملية للسحب والدفع الإلكتروني في الجزائر</description>\n"
        "    <language>ar-dz</language>\n"
        f"    <atom:link href=\"{SITE}/feed.xml\" rel=\"self\" type=\"application/rss+xml\"/>\n"
        f"    <lastBuildDate>{NOW.strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>\n"
        + "\n".join(items) + "\n"
        "  </channel>\n"
        "</rss>\n"
    )


# ---------------------------------------------------------------- حقن الوسوم
def head_block(m):
    lines = [
        f'<link rel="canonical" href="{m["url"]}">',
        f'<meta property="og:url" content="{m["url"]}">',
        f'<meta property="og:image" content="{OG_IMAGE}">',
        '<meta property="og:locale" content="ar_DZ">',
        f'<link rel="alternate" type="application/rss+xml" title="كريبتو جزائر — RSS" href="{SITE}/feed.xml">',
    ]
    return "\n".join(lines)


def jsonld_block(m, kind):
    if kind == "home":
        data = [
            {"@context": "https://schema.org", "@type": "WebSite",
             "name": "كريبتو جزائر", "url": SITE,
             "inLanguage": "ar", "description": m["desc"]},
            {"@context": "https://schema.org", "@type": "Organization",
             "name": "كريبتو جزائر", "url": SITE,
             "logo": OG_IMAGE},
        ]
    else:
        pub = git_date(ROOT / m["rel"], last=False) or "2026-01-01"
        art = {"@context": "https://schema.org", "@type": "Article",
               "headline": m["title"], "description": m["desc"],
               "inLanguage": "ar", "mainEntityOfPage": m["url"],
               "datePublished": pub, "dateModified": m["lastmod"],
               "author": {"@type": "Organization", "name": "كريبتو جزائر", "url": SITE},
               "publisher": {"@type": "Organization", "name": "كريبتو جزائر", "url": SITE},
               "image": OG_IMAGE}
        if m["rel"] == f"articles/{PRICE_REPORT}":
            art["about"] = "أسعار البيتكوين والإيثيريوم وUSDT بالدينار الجزائري"
        data = [art]
    return "\n".join(
        '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False) + "</script>"
        for d in data)


def share_block(m):
    from urllib.parse import quote
    text = quote(f"{m['title']} — {m['url']}")
    url_q = quote(m["url"])
    t = quote(m["title"])
    return (
        '<div class="share-bar">'
        '<span class="share-label">📤 شارك هذا الدليل:</span>'
        f'<a class="share-btn wa" href="https://wa.me/?text={text}" target="_blank" rel="noopener" title="واتساب">واتساب</a>'
        f'<a class="share-btn fb" href="https://www.facebook.com/sharer/sharer.php?u={url_q}" target="_blank" rel="noopener" title="فيسبوك">فيسبوك</a>'
        f'<a class="share-btn tw" href="https://twitter.com/intent/tweet?text={t}&url={url_q}" target="_blank" rel="noopener" title="X">X</a>'
        f'<a class="share-btn tg" href="https://t.me/share/url?url={url_q}&text={t}" target="_blank" rel="noopener" title="تيليجرام">تيليجرام</a>'
        '<button class="share-btn cp" data-url="' + m["url"] + '" onclick="copyShareLink()">نسخ الرابط</button>'
        "</div>"
        + copy_js()
    )


def copy_js():
    return (
        "<script>\n"
        "function copyShareLink(){\n"
        "  var btns=document.querySelectorAll('.share-btn.cp');\n"
        "  var u=btns.length?btns[0].getAttribute('data-url'):'';\n"
        "  if(!u){u=location.href;}\n"
        "  navigator.clipboard.writeText(u).then(function(){\n"
        "    alert('تم نسخ الرابط ✅ شاركه مع من يحتاجه');\n"
        "  });\n"
        "}\n"
        "</script>"
    )


SHARE_CSS = """.share-bar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:24px auto;padding:14px 16px;max-width:720px;background:#f0fdfa;border:1px solid #22d3a5;border-radius:12px;font-size:14px}
.share-label{font-weight:700;color:#0f766e;margin-inline-end:4px}
.share-btn{display:inline-block;padding:8px 14px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;border:none;cursor:pointer;color:#fff;transition:transform .15s,box-shadow .15s}
.share-btn:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.15)}
.share-btn.wa{background:#25d366}.share-btn.fb{background:#1877f2}.share-btn.tw{background:#0f1419}.share-btn.tg{background:#229ed9}.share-btn.cp{background:#0f766e}"""


def inject_all(metas, clean=False):
    changed = []
    for kind, rel in collect_pages():
        m = next(x for x in metas if x["rel"] == rel)
        text = read(rel)
        orig = text

        # 1) كتلة الـ head (canonical/og/rss)
        hb = "" if clean else head_block(m) + "\n" + jsonld_block(m, "home" if rel == "index.html" else "article")
        blk = between_replace(text, HEAD_START, HEAD_END, hb)
        if blk is None:
            if clean:
                text = text.replace(HEAD_START + "\n" + HEAD_END + "\n", "").replace(HEAD_START + HEAD_END + "\n", "")
            else:
                text = text.replace("</head>",
                                    HEAD_START + "\n" + hb + "\n" + HEAD_END + "\n</head>", 1)
        else:
            text = blk

        # 2) شريط المشاركة — للمقالات فقط (وليس صفحات الجذر)
        if rel.startswith("articles/"):
            sb = "" if clean else share_block(m)
            blk = between_replace(text, SHARE_START, SHARE_END, sb)
            if blk is None:
                if clean:
                    text = text.replace(SHARE_START + "\n" + SHARE_END + "\n", "").replace(SHARE_START + SHARE_END + "\n", "")
                else:
                    text = text.replace("</article>",
                                        "</article>\n\n" + SHARE_START + "\n" + sb + "\n" + SHARE_END, 1)
            else:
                text = blk

        if text != orig:
            (ROOT / rel).write_text(text, encoding="utf-8")
            changed.append(rel)

    # 3) CSS شريط المشاركة
    css_path = ROOT / "assets" / "style.css"
    css = css_path.read_text(encoding="utf-8")
    pat = re.compile(re.escape(CSS_START) + r".*?" + re.escape(CSS_END), re.DOTALL)
    if clean:
        new_css = pat.sub("", css)
        new_css = re.sub(r"\n{3,}", "\n\n", new_css)
    elif pat.search(css):
        new_css = pat.sub(CSS_START + "\n" + SHARE_CSS + "\n" + CSS_END, css, count=1)
    else:
        new_css = css.rstrip("\n") + "\n\n" + CSS_START + "\n" + SHARE_CSS + "\n" + CSS_END + "\n"
    if new_css != css:
        css_path.write_text(new_css, encoding="utf-8")
        changed.append("assets/style.css")

    return changed


# ---------------------------------------------------------------- مفتاح IndexNow
def ensure_indexnow_key():
    """إنشاء ملف مفتاح IndexNow مرة واحدة (إن لم يوجد) — يسرّع فهرسة Bing/Yandex."""
    keys = [p for p in ROOT.glob("*.txt") if p.stem != "robots" and len(p.stem) == 32 and re.fullmatch(r"[0-9a-f]{32}", p.stem)]
    if keys:
        return keys[0].stem
    key = uuid.uuid4().hex
    (ROOT / f"{key}.txt").write_text(key, encoding="utf-8")
    return key


# ---------------------------------------------------------------- التنفيذ
def main():
    clean = "--clean" in sys.argv
    metas = [page_meta(rel) for _, rel in collect_pages()]

    if clean:
        changed = inject_all(metas, clean=True)
        for f in ("sitemap.xml", "robots.txt", "feed.xml"):
            p = ROOT / f
            if p.exists():
                p.unlink()
                changed.append(f + " (حُذف)")
        print(f"=== تنظيف SEO: {len(changed)} تغيير ===")
        for c in changed:
            print("  -", c)
        return

    changed = []
    if write("sitemap.xml", build_sitemap(metas)):
        changed.append("sitemap.xml")
    if write("robots.txt", build_robots()):
        changed.append("robots.txt")
    if write("feed.xml", build_feed(metas)):
        changed.append("feed.xml")

    changed += inject_all(metas)
    key = ensure_indexnow_key()
    print(f"مفتاح IndexNow: {key}")

    print(f"=== توليد SEO: {len(metas)} صفحة، {len(changed)} تغيير ===")
    for c in changed:
        print("  -", c)
    if not changed:
        print("  (كل شيء محدّث — لا تغييرات)")


if __name__ == "__main__":
    main()
