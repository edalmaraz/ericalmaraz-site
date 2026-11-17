# ericalmaraz.com

Personal portfolio site for Eric Almaraz: a playable home page ("Run the morning"), five case
studies of systems he built and runs, and an about page. Static HTML, CSS and vanilla
JavaScript. No frameworks, no external requests, self-hosted fonts.

Employer, brand and customer names are deliberately absent from every page, from this
repository and from its commit history. Keep it that way.

## Layout

| Path | What it is |
|---|---|
| `src/base.html` | Shared page shell (head, masthead, footer) |
| `src/pages/` | One file per page: a front-matter comment, then the page body |
| `docs/` | The built site. GitHub Pages serves this folder |
| `docs/assets/` | Stylesheet, scripts, fonts (SIL OFL, licences alongside), link-preview card |
| `tools/build.py` | Builds `src/` into `docs/` |
| `tools/verify_site.py` | Static checks: links, metadata, privacy terms, page weight |
| `tools/livecheck.py` | Drives the real controls in headless Edge and checks the results |
| `tools/shots.sh` | Review screenshots, print-PDF page counts, and `docs/assets/og.png` |

## Build and check

```
py -3.13 tools/build.py          # preview build: noindex on every page, no CNAME
py -3.13 tools/verify_site.py    # must end with PASS
py -3.13 tools/livecheck.py      # must end with PASS (about a minute)
bash tools/shots.sh              # screenshots into shots/ (git-ignored)
```

`verify_site.py` reads its banned-terms list from a file kept outside this repository
(set the `SITE_BANNED_TERMS` environment variable to your private list, or pass `--banned`). The list itself names
the things that must never appear here, so it must never be committed.

Edit pages in `src/pages/`, then rebuild. Do not edit the HTML in `docs/` by hand. The
stylesheet and scripts in `docs/assets/` are edited in place.

## Preview

Open `docs/index.html` in a browser; every page works from a double-clicked file.

Motion: the site follows the visitor's reduced-motion setting and shows a calm, stepped
version when it is on. The "Play with motion" button (top right, and inside the console)
switches to the animated version and remembers the choice. Nothing depends on a query string.

## Truth rules for content

- Every number comes from a system's own logs or notes, and each case study says how it was
  counted and what was not measured. Do not add a figure without a source.
- "Built and run by me." Never write that a team or the company adopted a tool.
- Demos are labelled as illustrations; game counts are visibly a game.
- No em dashes, no phone, no email, no photo, no resume file.

## Launch checklist

The repository ships in preview mode. To go live on the custom domain:

1. **Decide whether to add a resume link.** There is none today. If one is added, it has to
   fit the privacy rules above.
2. **Confirm the support escalation sweep wording.** Its page says "built to run twice each
   weekday" and quotes only first-week figures, because recent runs were not re-counted.
3. **Build for launch:** `py -3.13 tools/build.py --launch` (removes `noindex`, writes
   `docs/CNAME` with `ericalmaraz.com`), then `py -3.13 tools/verify_site.py --launch`.
4. **GitHub Pages:** serve the `main` branch, `/docs` folder; set the custom domain to
   `ericalmaraz.com`.
5. **DNS at the registrar (Squarespace-managed domain).** This replaces the old site.
   - `A` records for the apex: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`,
     `185.199.111.153`
   - `CNAME` for `www`: `<github-user>.github.io`
   - Remove the old `www` record that points at the previous host.
6. **Enable "Enforce HTTPS"** in the Pages settings once the certificate is issued.
7. Paste the address into a chat app and an email to check the link-preview card.
