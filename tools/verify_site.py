"""Verify the built site in docs/. Python stdlib only.

    py -3.13 tools/verify_site.py            preview mode (expects noindex, no CNAME)
    py -3.13 tools/verify_site.py --launch   launch mode  (expects CNAME, no noindex)

Checks: banned terms (list kept outside the repo), internal links, relative paths, no external
requests, per-page metadata, no em dash, no query-string dependence, required pages, page weight,
and no local absolute paths in tracked files or in history.

The banned-terms list is private. Point the SITE_BANNED_TERMS environment variable at it
(or pass --banned). The verifier refuses to run without it.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BANNED_ENV = "SITE_BANNED_TERMS"   # path to a private list kept outside this repository

LINKEDIN = "https://www.linkedin.com/in/eric-almaraz-40717122"
SITE = "https://ericalmaraz.com"
REQUIRED = [
    "index.html", "about.html", "404.html", "favicon.svg", "robots.txt", "sitemap.xml",
    "assets/og.png", "assets/site.css", "assets/site.js",
    "work/proof-of-delivery-archive.html", "work/support-escalation-sweep.html",
    "work/automation-health-monitor.html", "work/ai-gateway.html", "work/daily-operations-steward.html",
]
TEXT_EXT = {".html", ".css", ".js", ".svg", ".xml", ".txt", ".md", ".py", ".json", ".sh", ""}
ALLOWED_EMAILS = re.compile(r"[\w.+-]+@users\.noreply\.github\.com|noreply@anthropic\.com", re.I)
WEIGHT_WARN = 150 * 1024
EM_DASH = "\u2014"

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.title = ""
        self._in_title = False
        self.h1 = 0
        self.metas: dict[str, str] = {}
        self.refs: list[tuple[str, str, str]] = []   # (tag, attr, value)
        self.ids: set[str] = set()
        self.has_footer = False
        self.canonical = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a and a["id"]:
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta":
            key = a.get("name") or a.get("property")
            if key:
                self.metas[key.lower()] = a.get("content") or ""
        elif tag == "footer" and "colophon" in (a.get("class") or ""):
            self.has_footer = True
        if tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = a.get("href")
        for attr in ("href", "src", "poster", "action", "data"):
            if a.get(attr) is not None:
                self.refs.append((tag, attr, a[attr]))
        if a.get("srcset"):
            for part in a["srcset"].split(","):
                self.refs.append((tag, "srcset", part.strip().split(" ")[0]))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        return [ROOT / line for line in out.splitlines() if line.strip()]
    except Exception:
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


def read_text(p: Path) -> str | None:
    if p.suffix.lower() not in TEXT_EXT:
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def check_banned(banned_path: Path) -> None:
    if not banned_path.exists():
        err("banned-terms list not found (set SITE_BANNED_TERMS or --banned)")
        return
    pats = []
    for line in banned_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pats.append(re.compile(line, re.I))
    sources: list[tuple[str, str]] = []
    for p in tracked_files():
        if not p.exists():
            continue
        name = str(p.relative_to(ROOT)).replace("\\", "/")
        if name.startswith("docs/assets/fonts/OFL"):
            continue  # third-party licence text
        text = read_text(p)
        sources.append((name + " (file name)", name))
        if text is not None:
            sources.append((name, text))
    try:
        log = subprocess.run(["git", "log", "-p", "--all", "--format=%B%n%ae%n%ce%n%an%n%cn"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        sources.append(("git log", log))
    except Exception:
        warnings.append("git log could not be read")
    hits = 0
    for name, text in sources:
        clean = ALLOWED_EMAILS.sub("", text)
        for pat in pats:
            for m in pat.finditer(clean):
                hits += 1
                line_no = clean.count("\n", 0, m.start()) + 1
                # do not echo the term itself; it must not land in logs that get committed
                err(f"banned term (pattern #{pats.index(pat) + 1}) in {name}:{line_no}")
    return


# Local absolute paths must never be published: searched as fixed strings and as patterns.
LOCAL_PATH_FIXED = [":" + chr(92) + "Users" + chr(92), "/" + "Users/", "/" + "home/"]
LOCAL_PATH_RE = re.compile(r"[A-Za-z]:[" + chr(92) * 2 + r"/]+Users[" + chr(92) * 2 + r"/]|(?<![\w.])/(?:Users|home)/[\w.-]+", re.I)


def check_local_paths() -> None:
    sources: list[tuple[str, str]] = []
    for p in tracked_files():
        if not p.exists():
            continue
        name = str(p.relative_to(ROOT)).replace(chr(92), "/")
        if name.startswith("docs/assets/fonts/OFL"):
            continue
        text = read_text(p)
        if text is not None:
            sources.append((name, text))
    try:
        hist = subprocess.run(["git", "log", "-p", "--all", "--format=%H%n%B%n%ae%n%ce"], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        sources.append(("git history", hist))
    except Exception:
        warnings.append("git history could not be read")
    for name, text in sources:
        for n, line in enumerate(text.splitlines(), 1):
            if any(f in line for f in LOCAL_PATH_FIXED) or LOCAL_PATH_RE.search(line):
                err(f"local absolute path in {name}:{n}")
                break


def check_pages(launch: bool) -> dict[str, int]:
    weights: dict[str, int] = {}
    titles: dict[str, str] = {}
    pages = sorted(DOCS.rglob("*.html"))
    parsed: dict[Path, Page] = {}
    for p in pages:
        pg = Page()
        pg.feed(p.read_text(encoding="utf-8"))
        parsed[p] = pg
    for p, pg in parsed.items():
        rel = str(p.relative_to(DOCS)).replace("\\", "/")
        is_404 = rel == "404.html"
        if pg.lang != "en":
            err(f"{rel}: <html lang> missing")
        if not pg.title.strip():
            err(f"{rel}: empty <title>")
        elif pg.title in titles:
            err(f"{rel}: title duplicates {titles[pg.title]}")
        titles[pg.title] = rel
        if pg.h1 != 1:
            err(f"{rel}: expected exactly one h1, found {pg.h1}")
        if "viewport" not in pg.metas:
            err(f"{rel}: viewport meta missing")
        if not pg.metas.get("description"):
            err(f"{rel}: meta description missing")
        for og in ("og:title", "og:description", "og:image", "og:type"):
            if not pg.metas.get(og):
                err(f"{rel}: {og} missing")
        if not pg.has_footer:
            err(f"{rel}: shared footer missing")
        robots = pg.metas.get("robots", "")
        if launch and "noindex" in robots and not is_404:
            err(f"{rel}: still has preview noindex")
        if not launch and "noindex" not in robots:
            err(f"{rel}: preview build must carry noindex")

        weight = p.stat().st_size
        for tag, attr, val in pg.refs:
            v = val.strip()
            if v.startswith(("mailto:", "tel:", "javascript:")):
                err(f"{rel}: forbidden link scheme in {v[:20]}")
                continue
            if re.match(r"^(https?:)?//", v):
                ok = v == LINKEDIN or (tag == "link" and v.startswith(SITE))
                if not ok:
                    err(f"{rel}: external reference {v}")
                continue
            if v.startswith("data:"):
                continue
            if "?" in v:
                err(f"{rel}: link depends on a query string: {v}")
            if v.startswith("/"):
                err(f"{rel}: root-absolute path {v} (must be relative)")
                continue
            path, _, frag = v.partition("#")
            target = p if path == "" else (p.parent / path).resolve()
            if path.endswith("/") or path in (".", ".."):
                target = target / "index.html"
            if not target.exists():
                err(f"{rel}: broken link {v}")
                continue
            try:
                target.relative_to(DOCS.resolve())
            except ValueError:
                err(f"{rel}: link leaves the site: {v}")
                continue
            if frag and target.suffix == ".html":
                tp = parsed.get(target) or parsed.get(Path(str(target)))
                if tp is None:
                    for k in parsed:
                        if k.resolve() == target:
                            tp = parsed[k]
                if tp is not None and frag not in tp.ids:
                    err(f"{rel}: anchor #{frag} not found in {target.name}")
            if tag in ("script", "link") and target.suffix in (".css", ".js"):
                weight += target.stat().st_size
        weights[rel] = weight
        if weight > WEIGHT_WARN:
            warnings.append(f"{rel}: {weight / 1024:.0f} KB of HTML+CSS+JS (budget 150 KB)")
    return weights


def check_text_rules() -> None:
    for p in sorted(DOCS.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(DOCS)).replace("\\", "/")
        if rel.startswith("assets/fonts/OFL"):
            continue
        text = read_text(p)
        if text is None:
            continue
        if EM_DASH in text:
            err(f"{rel}: contains an em dash")
        if p.suffix in (".js", ".html") and re.search(r"location\.search|URLSearchParams|searchParams", text):
            err(f"{rel}: reads the query string")
        # any absolute URL outside the allowed set
        for m in re.finditer(r"""(?:https?:)?//[A-Za-z0-9][^\s"'<>)]*""", text):
            url = m.group(0)
            if not url.startswith("http"):
                # protocol-relative only counts when it looks like a host
                before = text[max(0, m.start() - 1):m.start()]
                if before in (":", "/", "*", " ", "\n", "\t", "") or not re.match(r"//[\w-]+\.[a-z]{2,}", url):
                    continue
            if url.startswith(LINKEDIN) or url.startswith(SITE) or url.startswith(("http://www.w3.org/", "http://www.sitemaps.org/schemas/")):
                continue
            err(f"{rel}: external URL {url}")
        if p.suffix == ".css":
            for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)", text):
                u = m.group(1)
                if u.startswith("data:"):
                    continue
                if re.match(r"^(https?:)?//", u) or u.startswith("/"):
                    err(f"{rel}: non-relative url({u})")
                elif not (p.parent / u.split("#")[0].split("?")[0]).exists():
                    err(f"{rel}: missing asset url({u})")
            if "@import" in text:
                err(f"{rel}: @import is not allowed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--launch", action="store_true")
    ap.add_argument("--banned", type=Path, default=None)
    args = ap.parse_args()
    banned = args.banned or (Path(os.environ[BANNED_ENV]) if os.environ.get(BANNED_ENV) else None)
    if banned is None:
        print(f"verify_site: set {BANNED_ENV} to your private banned-terms list, or pass --banned. Not run.")
        return 2
    if not banned.is_file():
        print("verify_site: the banned-terms list was not found at the configured location. Not run.")
        return 2

    if not DOCS.exists():
        err("docs/ does not exist; run tools/build.py first")
    else:
        for r in REQUIRED:
            if not (DOCS / r).exists():
                err(f"required file missing: docs/{r}")
        cname = DOCS / "CNAME"
        if args.launch and not cname.exists():
            err("launch build needs docs/CNAME")
        if not args.launch and cname.exists():
            err("preview build must not ship docs/CNAME (it would redirect the preview address)")
        weights = check_pages(args.launch)
        check_text_rules()
        print("Page weight (HTML + CSS + JS, fonts and images excluded):")
        for rel, w in sorted(weights.items()):
            print(f"  {w / 1024:6.1f} KB  {rel}")
    check_banned(banned)
    check_local_paths()

    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("FAIL ", e)
    mode = "launch" if args.launch else "preview"
    pages = len(list(DOCS.rglob("*.html"))) if DOCS.exists() else 0
    print(f"verify_site [{mode}]: {pages} pages, {len(errors)} errors, {len(warnings)} warnings: "
          + ("PASS" if not errors else "FAIL"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
