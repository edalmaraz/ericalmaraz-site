#!/usr/bin/env bash
# Render review screenshots and print-PDFs with headless Edge, using a throwaway profile.
# Output goes to shots/ (git-ignored). Also renders docs/assets/og.png from tools/og.html.
#   bash tools/shots.sh            everything
#   bash tools/shots.sh og         only the link-preview card
set -u
cd "$(dirname "$0")/.."
ROOT_W="$(cygpath -m "$PWD")"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
PROFILE="$(mktemp -d)"
mkdir -p shots
only="${1:-all}"

shot() { # out width height url [budget]
  "$EDGE" --headless=new --disable-gpu --hide-scrollbars --user-data-dir="$(cygpath -w "$PROFILE")" \
    --virtual-time-budget="${5:-3500}" --window-size="$2,$3" --screenshot="$(cygpath -w "$PWD/$1")" "$4" >/dev/null 2>&1
}
helper() { # page w h extra-query
  echo "file:///$ROOT_W/tools/shot.html?page=$1&w=$2&h=$3$4"
}

shot docs/assets/og.png 1200 630 "file:///$ROOT_W/tools/og.html"
[ "$only" = "og" ] && { rm -rf "$PROFILE"; exit 0; }
# "pdf" skips the screenshots and only prints

# name:page:desktop-height:mobile-height
PAGES="
index:index.html:3900:6400
about:about.html:2700:3900
archive:work/proof-of-delivery-archive.html:3900:6000
sweep:work/support-escalation-sweep.html:4100:6600
monitor:work/automation-health-monitor.html:3900:6400
gateway:work/ai-gateway.html:3900:6200
steward:work/daily-operations-steward.html:4000:6400
lost:404.html:900:900
"
for row in $PAGES; do
  [ "$only" = "pdf" ] && break
  IFS=: read -r name page dh mh <<<"$row"
  st=""; [ "$name" != "index" ] && [ "$name" != "about" ] && [ "$name" != "lost" ] && st="&state=end"
  shot "shots/$name-desk.png" 1440 "$dh" "$(helper "$page" 1440 "$dh" "&motion=off$st")"
  shot "shots/$name-mob.png" 390 "$mh" "$(helper "$page" 390 "$mh" "&motion=off$st")"
done

if [ "$only" != "pdf" ]; then
# the game: first view (calm, as on a reduced-motion device), mid and finished states, and with motion on
shot shots/game-first-calm.png 1440 900 "$(helper index.html 1440 900 "&motion=off&state=first")"
shot shots/game-mid.png 1440 900 "$(helper index.html 1440 900 "&motion=on&state=mid")"
shot shots/game-done.png 1440 1500 "$(helper index.html 1440 1500 "&motion=on&state=done")"
shot shots/game-live.png 1440 900 "$(helper index.html 1440 900 "&motion=on")" 9000
shot shots/game-mid-mob.png 390 1500 "$(helper index.html 390 1500 "&motion=off&state=mid")"
shot shots/game-done-mob.png 390 1900 "$(helper index.html 390 1900 "&motion=off&state=done")"
fi

# print to PDF and count pages
for row in $PAGES; do
  IFS=: read -r name page dh mh <<<"$row"
  [ "$name" = "lost" ] && continue
  "$EDGE" --headless=new --disable-gpu --user-data-dir="$(cygpath -w "$PROFILE")" --no-pdf-header-footer \
    --print-to-pdf="$(cygpath -w "$PWD/shots/$name.pdf")" "file:///$ROOT_W/docs/$page" >/dev/null 2>&1
done
py -3.13 - <<'PY'
import re, pathlib
for p in sorted(pathlib.Path("shots").glob("*.pdf")):
    data = p.read_bytes()
    counts = [int(m) for m in re.findall(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", data)] or [int(m) for m in re.findall(rb"/Count\s+(\d+)", data)]
    print(f"{p.name}: {max(counts) if counts else '?'} page(s)")
PY
rm -rf "$PROFILE"
