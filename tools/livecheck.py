"""Functional smoke test in a real (headless) browser, in real time. Python stdlib only.

    py -3.13 tools/livecheck.py

Serves docs/ on 127.0.0.1 for a few seconds, drives each page from a same-origin test frame
(clicking the real controls), and checks what happened. Headless Edge takes its DOM dump at
window load, so the test page holds its load open with a deliberately slow image while the
steps run. Uses a throwaway browser profile; never touches a running browser.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
HOLD_MS = 9000

COMMON = r"""
var out = {}, f = document.getElementById('f');
function doc() { return f.contentDocument; }
function q(s) { return doc().querySelector(s); }
function qa(s) { return Array.prototype.slice.call(doc().querySelectorAll(s)); }
function done() { document.getElementById('out').textContent = JSON.stringify(out); }
function at(ms, fn) { setTimeout(function () { try { fn(); } catch (e) { out.error = String(e); } done(); }, ms); }
"""

CASES = {
    "game": ("index.html", r"""
f.addEventListener('load', function () {
  out.startClass = doc().documentElement.className;
  out.toggleVisible = !q('[data-motion-toggle]').hidden;
  at(300, function () {
    q('.calm-note button').click();                       // "Play with motion" inside the console
    out.afterPlay = doc().documentElement.className;
    out.stored = f.contentWindow.localStorage.getItem('ea-motion');
    out.frames0 = +q('#console').getAttribute('data-frames');
  });
  at(3300, function () {
    out.frames1 = +q('#console').getAttribute('data-frames');
    out.deskMid = +q('#g-desk').textContent;
    out.ticketsMid = qa('.ticket').length;
    var sw = qa('.sw');
    sw[0].click(); out.on = sw[0].getAttribute('aria-checked');
    sw[0].click(); out.offAgain = sw[0].getAttribute('aria-checked');
    q('.pile').click();
    sw.forEach(function (b) { b.click(); });
  });
  at(6300, function () {
    out.doneClass = q('#console').className;
    out.deskEnd = +q('#g-desk').textContent;
    out.caught = +q('#g-caught').textContent;
    out.tapeShown = !q('#tape').hidden;
    out.status = q('#g-status').textContent;
    qa('.sw')[2].click();                                  // switch one off after the finish
    out.afterOff = q('#console').className;
  });
});
"""),
    "persist": ("about.html", r"""
// a second page in the same browser profile: the choice made on the home page must carry over
var once = false;
f.addEventListener('load', function () {
  if (once) return; once = true;
  f.contentWindow.localStorage.setItem('ea-motion', 'on');
  f.contentWindow.location.reload();
  at(1500, function () {
    out.cls = doc().documentElement.className;
    out.label = q('[data-motion-toggle]').textContent;
    q('[data-motion-toggle]').click();
    out.clsAfter = doc().documentElement.className;
    out.stored = f.contentWindow.localStorage.getItem('ea-motion');
  });
});
"""),
    "archive": ("work/proof-of-delivery-archive.html", r"""
f.addEventListener('load', function () {
  at(400, function () {
    var r = q('#exp-range'); r.value = 90; r.dispatchEvent(new Event('input'));
    out.gone = q('#exp-carrier').className; out.ask = q('#exp-ask').textContent; out.label = q('#exp-out').textContent;
  });
});
"""),
    "sweep": ("work/support-escalation-sweep.html", r"""
f.addEventListener('load', function () {
  at(400, function () {
    out.hiddenBefore = qa('.draft .verdict').filter(function (v) { return getComputedStyle(v).display === 'none'; }).length;
    qa('.draft button').forEach(function (b) { b.click(); });
    out.shownAfter = qa('.draft .verdict').filter(function (v) { return getComputedStyle(v).display !== 'none'; }).length;
    out.say = q('#checker-say').textContent;
  });
});
"""),
    "monitor": ("work/automation-health-monitor.html", r"""
f.addEventListener('load', function () {
  at(400, function () { out.tiles = qa('#wall i').length; out.onlyDisabled = q('#wall-only').disabled; q('#wall-sweep').click(); });
  at(4000, function () {
    out.on = qa('#wall i.on').length; out.fail = qa('#wall i.fail').length; out.ok = qa('#wall i.ok').length;
    q('#wall-only').click(); out.only = q('#wall').className; out.say = q('#wall-say').textContent;
  });
});
"""),
    "gateway": ("work/ai-gateway.html", r"""
f.addEventListener('load', function () {
  at(400, function () { var a = qa('.avail'); a[0].click(); a[1].click(); out.first = a[0].getAttribute('aria-checked'); q('#gw-send').click(); });
  at(4000, function () {
    out.say = q('#gw-say').textContent; out.hit = qa('.rung').map(function (r) { return r.className; });
    qa('.avail')[2].click(); q('#gw-send').click();
  });
  at(7500, function () { out.sayAllOff = q('#gw-say').textContent; });
});
"""),
    "steward": ("work/daily-operations-steward.html", r"""
f.addEventListener('load', function () {
  at(400, function () {
    out.hiddenBefore = qa('.sheet ol li').filter(function (l) { return getComputedStyle(l).display === 'none'; }).length;
    qa('.chip')[4].click(); q('#brief-build').click();
  });
  at(5000, function () {
    out.linesIn = qa('.sheet ol li.in').length; out.sent = q('.sheet .sent').className; out.say = q('#brief-say').textContent;
  });
});
"""),
}

EXPECT = {
    "game": lambda o: [
        ("toggle button visible", o.get("toggleVisible") is True),
        ("Play with motion switches to motion", "motion" in o.get("afterPlay", "") and "calm" not in o.get("afterPlay", "")),
        ("choice stored", o.get("stored") == "on"),
        ("animation loop runs in real time (frames advance)", o.get("frames1", 0) - o.get("frames0", 0) > 30),
        ("trouble piles up", o.get("deskMid", 0) > 0),
        ("switch on", o.get("on") == "true"),
        ("switch off again", o.get("offAgain") == "false"),
        ("all five on clears the desk", o.get("deskEnd") == 0 and "done" in o.get("doneClass", "")),
        ("systems caught trouble", o.get("caught", 0) > 0),
        ("real figures revealed", o.get("tapeShown") is True),
        ("switching off after the finish leaves the done state", "done" not in o.get("afterOff", "done")),
    ],
    "persist": lambda o: [
        ("saved choice applies on another page", "motion" in o.get("cls", "")),
        ("toggle label follows", o.get("label") == "Reduce motion"),
        ("toggle back to calm and store it", "calm" in o.get("clsAfter", "") and o.get("stored") == "off"),
    ],
    "archive": lambda o: [("carrier record expires", "gone" in o.get("gone", "")), ("buyer line shown", "archive" in o.get("ask", ""))],
    "sweep": lambda o: [("verdicts hidden until checked", o.get("hiddenBefore") == 3), ("all verdicts shown", o.get("shownAfter") == 3),
                        ("status line", "One of three" in o.get("say", ""))],
    "monitor": lambda o: [("574 tiles", o.get("tiles") == 574), ("filter disabled before sweep", o.get("onlyDisabled") is True),
                          ("all tiles flipped", o.get("on") == 574), ("28 failing", o.get("fail") == 28), ("225 healthy", o.get("ok") == 225),
                          ("repair filter", "only-fail" in o.get("only", ""))],
    "gateway": lambda o: [("lane switched off", o.get("first") == "false"), ("falls back to lane 3", "lane 3" in o.get("say", "")),
                          ("all lanes off fails and is logged", "309 of 14,639" in o.get("sayAllOff", ""))],
    "steward": lambda o: [("lines hidden first", o.get("hiddenBefore") == 5), ("four lines after switching one source off", o.get("linesIn") == 4),
                          ("sent stamp", "in" in o.get("sent", "").split()), ("status line", "4 lines" in o.get("say", ""))],
}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/__slow":
            time.sleep(int(parse_qs(u.query).get("ms", ["1000"])[0]) / 1000)
            body = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
            self.send_response(200); self.send_header("Content-Type", "image/gif"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if u.path == "/__test":
            name = parse_qs(u.query)["case"][0]
            page, script = CASES[name]
            html = ("<!doctype html><meta charset='utf-8'><title>t</title>"
                    f"<iframe id='f' src='/{page}' style='width:1280px;height:900px;border:0'></iframe>"
                    "<pre id='out'>{}</pre>"
                    f"<script>{COMMON}{script}</script><img src='/__slow?ms={HOLD_MS}' alt=''>").encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(html)))
            self.end_headers(); self.wfile.write(html); return
        super().do_GET()


def main() -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(DOCS)))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    profile = tempfile.mkdtemp(prefix="ea-livecheck-")
    failed = 0
    try:
        for name in CASES:
            cmd = [EDGE, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", "--window-size=1300,1000",
                   "--dump-dom", f"http://127.0.0.1:{port}/__test?case={name}"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
            m = re.search(r'<pre id="out">(.*?)</pre>', res.stdout, re.S)
            try:
                o = json.loads(m.group(1).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")) if m else {}
            except json.JSONDecodeError:
                o = {}
            if o.get("error"):
                print(f"FAIL  {name}: script error {o['error']}"); failed += 1
            for label, ok in EXPECT[name](o):
                print(f"{'ok   ' if ok else 'FAIL '} {name}: {label}")
                failed += 0 if ok else 1
            if name == "game":
                print(f"       game: frames {o.get('frames0')} -> {o.get('frames1')} in 3 s, desk mid {o.get('deskMid')}, caught {o.get('caught')}")
    finally:
        srv.shutdown()
        shutil.rmtree(profile, ignore_errors=True)
    print(f"livecheck: {failed} failures: " + ("PASS" if not failed else "FAIL"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
