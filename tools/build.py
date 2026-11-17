"""Build the static site from src/ into docs/. Python stdlib only.

    py -3.13 tools/build.py            preview build (noindex on every page, no CNAME)
    py -3.13 tools/build.py --launch   launch build  (indexable, writes docs/CNAME)

Each file in src/pages/ starts with an HTML comment holding `key: value` lines
(title, description, class, scripts), followed by the page body. The body is wrapped in
src/base.html. `{{root}}` in a page becomes the relative path back to the site root, so the
site works at a domain root, under a sub-path, and from a double-clicked file.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DOCS = ROOT / "docs"
SITE = "https://ericalmaraz.com"
UPDATED = "16 November 2026"
UPDATED_ISO = "2026-11-16"


def parse(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\s*<!--(.*?)-->\s*", text, re.S)
    if not m:
        sys.exit(f"{path}: missing front-matter comment")
    meta = {}
    for line in m.group(1).strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--launch", action="store_true")
    args = ap.parse_args()

    base = (SRC / "base.html").read_text(encoding="utf-8")
    pages = sorted((SRC / "pages").rglob("*.html"))
    urls = []
    for src in pages:
        rel = src.relative_to(SRC / "pages").as_posix()
        meta, body = parse(src)
        depth = rel.count("/")
        root = "../" * depth
        is_404 = rel == "404.html"
        canonical = SITE + "/" + ("" if rel == "index.html" else rel)
        scripts = "".join(
            f'<script src="{root}assets/{s.strip()}" defer></script>\n'
            for s in meta.get("scripts", "").split(",") if s.strip())
        robots = '<meta name="robots" content="noindex">\n' if (not args.launch or is_404) else ""
        base_tag = ""
        if is_404:
            # a 404 page is served at any depth, so point relative links back at the site root
            base_tag = ("<script>(function(){var l=location,p=l.pathname.split('/'),b='/';"
                        "if(/github\\.io$/.test(l.hostname)&&p.length>2)b='/'+p[1]+'/';"
                        "if(l.protocol==='file:')b='./';"
                        "document.write('<base href=\"'+b+'\">');"
                        "document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a');"
                        "var h=a&&a.getAttribute('href');if(!h||h.charAt(0)!=='#')return;var t=document.getElementById(h.slice(1));"
                        "if(!t)return;e.preventDefault();t.scrollIntoView();if(t.tabIndex<0)t.tabIndex=-1;t.focus();});"
                        "})();</script>\n")
        out = base
        repl = {
            "body": body,
            "title": meta["title"],
            "description": meta["description"],
            "og_title": meta.get("og_title", meta["title"]),
            "class": meta.get("class", ""),
            "scripts": scripts,
            "robots": robots,
            "base_tag": base_tag,
            "canonical": canonical,
            "self": "",
            "skip_label": meta.get("skip", "Skip to the content"),
            "updated": UPDATED,
            "site": SITE,
            "nav_work": "true" if rel == "index.html" else "false",
        }
        for k, v in repl.items():
            out = out.replace("{{" + k + "}}", v)
        out = out.replace("{{root}}", root)
        left = re.findall(r"\{\{[a-z_]+\}\}", out)
        if left:
            sys.exit(f"{rel}: unresolved tokens {sorted(set(left))}")
        dest = DOCS / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8", newline="\n")
        if not is_404:
            urls.append(canonical)

    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{UPDATED_ISO}</lastmod></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8", newline="\n")
    (DOCS / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8", newline="\n")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    cname = DOCS / "CNAME"
    if args.launch:
        cname.write_text("ericalmaraz.com\n", encoding="utf-8", newline="\n")
    elif cname.exists():
        cname.unlink()
    print(f"built {len(pages)} pages into {DOCS} ({'launch' if args.launch else 'preview'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
