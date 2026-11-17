/* One small hands-on demo per case study. Each is an illustration of the idea, not live data.
   Every demo's content is in the HTML already; this only makes it something to press. */
(function () {
  'use strict';
  var EA = window.EA || { motion: function () { return false; } };
  var $ = function (id) { return document.getElementById(id); };
  function wait(ms) { return EA.motion() ? ms : 0; }
  function onState(fn) { document.addEventListener('ea-state', function (e) { fn(e.detail && e.detail.state); }); }

  /* ---------- 1. archive: drag time forward ---------- */
  (function () {
    var r = $('exp-range'); if (!r) return;
    var out = $('exp-out'), car = $('exp-carrier'), carS = $('exp-carrier-s'), ask = $('exp-ask');
    function draw() {
      var v = +r.value;
      out.textContent = v < 8 ? 'Delivery day' : v < 40 ? 'Weeks later' : v < 75 ? 'Months later' : 'Long after';
      var gone = v >= 55;
      car.classList.toggle('gone', gone);
      carS.textContent = gone ? 'Expired. The carrier no longer has it.' : 'Available from the carrier';
      ask.textContent = v >= 75 ? 'A buyer asks for proof now. Only the archive still has it.' : '';
      r.setAttribute('aria-valuetext', out.textContent + (gone ? ', carrier record expired, archive copy on file' : ', both copies available'));
    }
    r.addEventListener('input', draw);
    onState(function (s) { if (s === 'end') { r.value = 90; draw(); } });
    draw();
  })();

  /* ---------- 2. sweep: you are the checker ---------- */
  (function () {
    var box = $('checker'); if (!box) return;
    var say = $('checker-say');
    var drafts = box.querySelectorAll('.draft');
    box.classList.add('armed');
    function check(li) {
      if (li.classList.contains('checked')) return;
      li.classList.add('checked');
      var left = box.querySelectorAll('.draft:not(.checked)').length;
      var pass = li.getAttribute('data-verdict') === 'pass';
      say.textContent = (pass ? 'Passed, so it is published.' : 'Rejected, so nothing is published and I get an alert.') +
        (left ? ' ' + left + ' to go.' : ' One of three went out. That is the checker doing its job.');
    }
    Array.prototype.forEach.call(drafts, function (li) {
      var b = li.querySelector('button');
      b.hidden = false;
      b.addEventListener('click', function () { check(li); });
    });
    onState(function (s) { if (s === 'end') Array.prototype.forEach.call(drafts, check); });
  })();

  /* ---------- 3. monitor: the wall of tiles ---------- */
  (function () {
    var wall = $('wall'); if (!wall) return;
    var btn = $('wall-sweep'), only = $('wall-only'), say = $('wall-say');
    var counts = [['ok', +wall.getAttribute('data-ok')], ['fail', +wall.getAttribute('data-fail')],
                  ['warn', +wall.getAttribute('data-warn')], ['none', +wall.getAttribute('data-none')],
                  ['other', +wall.getAttribute('data-other')]];
    var kinds = [];
    counts.forEach(function (c) { for (var i = 0; i < c[1]; i++) kinds.push(c[0]); });
    /* fixed shuffle so the wall looks the same on every visit */
    var seed = 574;
    function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }
    for (var i = kinds.length - 1; i > 0; i--) { var j = Math.floor(rnd() * (i + 1)); var t = kinds[i]; kinds[i] = kinds[j]; kinds[j] = t; }
    var frag = document.createDocumentFragment();
    var tiles = kinds.map(function (k) { var el = document.createElement('i'); el.className = k; frag.appendChild(el); return el; });
    wall.appendChild(frag);
    wall.hidden = false;
    btn.parentNode.hidden = false;
    var swept = false, timers = [];

    function sweep() {
      timers.forEach(clearTimeout); timers = [];
      tiles.forEach(function (el) { el.classList.remove('on'); });
      wall.classList.remove('only-fail'); only.setAttribute('aria-pressed', 'false');
      say.textContent = 'Reading the schedulers on three machines.';
      var step = wait(1);
      if (!step) { tiles.forEach(function (el) { el.classList.add('on'); }); finish(); return; }
      var per = 24, n = 0;
      (function wave() {
        for (var k = 0; k < per && n < tiles.length; k++, n++) tiles[n].classList.add('on');
        if (n < tiles.length) timers.push(setTimeout(wave, 30)); else finish();
      })();
    }
    function finish() {
      swept = true; only.disabled = false; btn.textContent = 'Run it again';
      say.textContent = 'Every job has a tile. The red ones are the 28 that need repair, and the grey ones are the 293 that have no health check yet.';
    }
    btn.addEventListener('click', sweep);
    only.addEventListener('click', function () {
      if (!swept) return;
      var on = !wall.classList.contains('only-fail');
      wall.classList.toggle('only-fail', on);
      only.setAttribute('aria-pressed', on ? 'true' : 'false');
      say.textContent = on ? 'This is the view I open first: 28 jobs to repair, out of 574.' : 'All 574 jobs.';
    });
    only.disabled = true;
    onState(function (s) {
      if (s !== 'end') return;
      timers.forEach(clearTimeout); tiles.forEach(function (el) { el.classList.add('on'); }); finish();
    });
  })();

  /* ---------- 4. gateway: a request falls through the lanes ---------- */
  (function () {
    var box = $('gateway'); if (!box) return;
    var rungs = Array.prototype.slice.call(box.querySelectorAll('.rung'));
    var send = $('gw-send'), say = $('gw-say');
    var busy = false;
    send.hidden = false;
    function avail(li) { return li.querySelector('.avail').getAttribute('aria-checked') === 'true'; }
    rungs.forEach(function (li) {
      var b = li.querySelector('.avail');
      b.hidden = false;
      b.addEventListener('click', function () {
        if (busy) return;
        var on = b.getAttribute('aria-checked') !== 'true';
        b.setAttribute('aria-checked', on ? 'true' : 'false');
        b.querySelector('.st').textContent = on ? 'available' : 'at its limit';
        li.classList.toggle('off', !on);
        clear();
      });
    });
    function clear() { rungs.forEach(function (li) { li.classList.remove('try', 'hit'); }); }
    function run(i, depth) {
      if (i >= rungs.length) {
        busy = false; send.disabled = false;
        say.textContent = 'No lane could answer, so the call fails and is logged. In the real log that was 309 of 14,639 calls.';
        return;
      }
      var li = rungs[i];
      if (avail(li)) {
        li.classList.add('hit');
        busy = false; send.disabled = false;
        say.textContent = 'Answered by lane ' + (i + 1) + ', ' + li.getAttribute('data-name') + '. ' +
          (depth ? 'It fell back ' + depth + (depth === 1 ? ' step' : ' steps') + ' to get there, and the log says so.' : 'First choice, no fallback. The log records that too.');
        return;
      }
      li.classList.add('try');
      setTimeout(function () { run(i + 1, depth + 1); }, wait(480));
    }
    send.addEventListener('click', function () {
      if (busy) return;
      busy = true; send.disabled = true; clear();
      say.textContent = 'Request sent.';
      setTimeout(function () { run(0, 0); }, wait(250));
    });
    onState(function (s) {
      if (s !== 'end') return;
      var b = rungs[0].querySelector('.avail');
      b.setAttribute('aria-checked', 'false'); b.querySelector('.st').textContent = 'at its limit'; rungs[0].classList.add('off');
      clear(); rungs[0].classList.add('try'); rungs[1].classList.add('hit');
      say.textContent = 'Answered by lane 2, ' + rungs[1].getAttribute('data-name') + '. It fell back 1 step to get there, and the log says so.';
    });
  })();

  /* ---------- 5. steward: the morning brief assembles ---------- */
  (function () {
    var box = $('brief'); if (!box) return;
    var build = $('brief-build'), say = $('brief-say');
    var lines = Array.prototype.slice.call(box.querySelectorAll('.sheet ol li'));
    var sent = box.querySelector('.sent');
    var chips = Array.prototype.slice.call(box.querySelectorAll('.chip'));
    var timers = [];
    box.classList.add('armed');
    build.hidden = false;
    box.querySelector('.sources').hidden = false;
    chips.forEach(function (c) {
      c.addEventListener('click', function () {
        c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
      });
    });
    function reset() {
      timers.forEach(clearTimeout); timers = [];
      lines.forEach(function (l) { l.classList.remove('in'); });
      sent.classList.remove('in'); box.classList.remove('has-lines');
    }
    function go(instant) {
      reset();
      var want = {};
      chips.forEach(function (c) { if (c.getAttribute('aria-pressed') === 'true') want[c.getAttribute('data-src')] = true; });
      var picked = lines.filter(function (l) { return want[l.getAttribute('data-src')]; });
      if (!picked.length) { say.textContent = 'Nothing is switched on, so there is nothing to brief. Pick at least one source.'; return; }
      box.classList.add('has-lines');
      say.textContent = 'Gathering what changed overnight.';
      var gap = instant ? 0 : wait(420);
      picked.forEach(function (l, n) {
        timers.push(setTimeout(function () { l.classList.add('in'); }, gap * (n + 1)));
      });
      timers.push(setTimeout(function () {
        sent.classList.add('in');
        say.textContent = picked.length + (picked.length === 1 ? ' line' : ' lines') + ', ranked, on my phone before the day starts. Anything already raised stays quiet until it changes.';
        build.textContent = 'Build it again';
      }, gap * (picked.length + 1)));
    }
    build.addEventListener('click', function () { go(false); });
    onState(function (s) { if (s === 'end') go(true); });
  })();
})();
