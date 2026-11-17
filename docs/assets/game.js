/* "Run the morning": a small sorting-console game. Vanilla JS, no dependencies.
   Trouble falls down five lanes and piles up on the desk. Each rocker switch puts one system on
   the job; it catches its kind of trouble at the gate. Counts here are a game, not real data. */
(function () {
  'use strict';
  var mount = document.getElementById('morning');
  if (!mount) return;

  var LANES = [
    { name: 'Proof-of-delivery archive', short: 'Archive', problem: 'Proof expiring', what: 'expiring proof', tag: 'Expiring', icon: 'i-box' },
    { name: 'Support escalation sweep', short: 'Sweep', problem: 'Stale ticket', what: 'stale ticket', tag: 'Stale', icon: 'i-bubble' },
    { name: 'Automation health monitor', short: 'Monitor', problem: 'Job failed', what: 'failed job', tag: 'Job failed', icon: 'i-alert' },
    { name: 'No-metered-cost AI gateway', short: 'Gateway', problem: 'AI limit hit', what: 'AI limit', tag: 'AI limit', icon: 'i-spark' },
    { name: 'Daily operations steward', short: 'Steward', problem: 'Inbox flood', what: 'inbox flood', tag: 'Inbox', icon: 'i-mail' }
  ];
  var st = null;
  var EA = window.EA || { motion: function () { return document.documentElement.classList.contains('motion'); } };
  var reduce = !EA.motion();   /* calm, stepped version unless the visitor has motion on */
  var icon = function (id) { return '<svg aria-hidden="true" viewBox="0 0 24 24"><use href="#' + id + '"/></svg>'; };

  /* ---------- build the console ---------- */
  var html = '' +
    '<div class="console" id="console">' +
      '<div class="score">' +
        '<div class="clock"><b id="g-clock">8:00</b><span>a.m.</span></div>' +
        '<div class="desk"><b id="g-desk">0</b><span>on your desk</span></div>' +
        '<div class="caught"><b id="g-caught">0</b><span>caught by systems</span></div>' +
        '<div class="hand"><b id="g-hand">0</b><span>cleared by hand</span></div>' +
      '</div>' +
      '<div class="calm-note"><p>Calm version: no animation.</p><button type="button" data-motion-on>Play with motion</button></div>' +
      '<p class="status" id="g-status" role="status" aria-live="polite"></p>' +
      '<div class="lanes">';
  LANES.forEach(function (l, i) {
    html += '' +
      '<div class="lane l' + i + '" style="--i:' + i + '">' +
        '<div class="lane-head">' + icon(l.icon) + '<span>' + l.problem + '</span></div>' +
        '<div class="track">' +
          '<div class="gate"><i>0</i></div>' +
          '<button type="button" class="pile" aria-label="Clear one ' + l.what + ' by hand"></button>' +
        '</div>' +
        '<button type="button" class="sw" role="switch" aria-checked="false" aria-label="' + l.name + ', catches every ' + l.what + '">' +
          '<span class="rocker" aria-hidden="true"><span class="knob"></span></span>' +
          '<span class="lbl" aria-hidden="true"><span class="full">' + l.name + '</span><span class="short">' + l.short + '</span></span>' +
          '<span class="state" aria-hidden="true">off</span>' +
        '</button>' +
      '</div>';
  });
  html += '</div>' +
      '<div class="console-foot"><p>A game. The real figures are below.</p>' +
      '<div><button type="button" id="g-pause">Pause</button><button type="button" id="g-reset">Start over</button></div></div>' +
    '</div>';
  mount.innerHTML = html;
  mount.hidden = false;

  var consoleEl = document.getElementById('console');
  var tape = document.getElementById('tape');
  var elClock = document.getElementById('g-clock'), elDesk = document.getElementById('g-desk'),
      elCaught = document.getElementById('g-caught'), elHand = document.getElementById('g-hand'),
      elStatus = document.getElementById('g-status'), btnPause = document.getElementById('g-pause');

  var lanes = Array.prototype.map.call(mount.querySelectorAll('.lane'), function (el, i) {
    return {
      i: i, el: el, def: LANES[i], on: false, pile: [], caught: 0,
      track: el.querySelector('.track'), gate: el.querySelector('.gate'), gateN: el.querySelector('.gate i'),
      sw: el.querySelector('.sw'), state: el.querySelector('.state'), pileBtn: el.querySelector('.pile')
    };
  });

  /* ---------- state ---------- */
  var tickets = [], t = 0, spawnIn = 0.5, burst = 0, caught = 0, hand = 0, done = false, instant = false;
  var running = false, userPaused = false, visible = true, last = 0, raf = 0;
  var frames = 0;
  var geo = { h: 0, gate: 0, th: 0, step: 0, max: 0 };

  function measure() {
    var tr = lanes[0].track;
    geo.h = tr.clientHeight || 376;
    geo.gate = geo.h * 0.30;
    geo.th = geo.h < 320 ? 29 : 34;
    geo.step = geo.h < 320 ? 13 : 15;
    geo.max = Math.max(4, Math.floor((geo.h - geo.gate - geo.th - 34) / geo.step));
    lanes.forEach(function (l) { l.pile.forEach(function (k, n) { k.y = slotY(n); place(k); }); });
  }
  function slotY(n) { return geo.h - 12 - geo.th - n * geo.step; }
  function place(k) { k.el.style.transform = 'translate3d(' + k.dx + 'px,' + k.y.toFixed(1) + 'px,0) rotate(' + k.rot + 'deg)'; }
  function deskCount() { return lanes.reduce(function (s, l) { return s + l.pile.length; }, 0); }
  function allOn() { return lanes.every(function (l) { return l.on; }); }

  function setNum(el, v) {
    var s = String(v);
    if (el.textContent === s) return;
    el.textContent = s;
    if (instant || reduce) return;
    el.classList.remove('bump'); void el.offsetWidth; el.classList.add('bump');
  }
  function say(msg) { if (elStatus.textContent !== msg) elStatus.textContent = msg; }

  /* ---------- tickets ---------- */
  function spawn() {
    var open = lanes.filter(function (l) { return l.on || l.pile.length < geo.max; });
    if (!open.length) return;
    var l = open[Math.floor(Math.random() * open.length)];
    var el = document.createElement('div');
    el.className = 'ticket';
    el.innerHTML = '<span>' + icon(l.def.icon) + '<em>' + l.def.tag + '</em></span>';
    var k = { lane: l, el: el, y: -geo.th, v: (geo.h / 376) * (190 + Math.random() * 90), s: 'fall', dx: (Math.random() * 8 - 4), rot: 0, wait: 0 };
    if (reduce || instant) {            /* stepped version: no falling */
      if (l.on) { l.caught++; caught++; l.gateN.textContent = l.caught; return; }
      l.track.appendChild(el); tickets.push(k); land(k); return;
    }
    l.track.appendChild(el); tickets.push(k); place(k);
  }
  function land(k) {
    var l = k.lane;
    k.s = 'piled'; k.y = slotY(l.pile.length); k.rot = +(Math.random() * 12 - 6).toFixed(1);
    l.pile.push(k); place(k);
  }
  function remove(k) {
    var n = tickets.indexOf(k); if (n > -1) tickets.splice(n, 1);
    if (k.el.parentNode) k.el.parentNode.removeChild(k.el);
  }
  function catchIt(k) {
    var l = k.lane;
    k.s = 'gone'; l.caught++; caught++; l.gateN.textContent = l.caught;
    if (instant || reduce) { remove(k); return; }
    k.el.classList.add('caught');
    l.gate.classList.remove('hit'); void l.gate.offsetWidth; l.gate.classList.add('hit');
    setTimeout(function () { remove(k); }, 330);
  }
  function clearByHand(l) {
    var k = l.pile.pop(); if (!k) return;
    k.s = 'gone'; hand++;
    if (instant || reduce) { remove(k); } else { k.el.classList.add('tossed'); setTimeout(function () { remove(k); }, 390); }
    refresh();
  }

  function toggle(l, on) {
    l.on = on;
    l.el.classList.toggle('on', on);
    l.sw.setAttribute('aria-checked', on ? 'true' : 'false');
    l.state.textContent = on ? 'on the job' : 'off';
    if (on) {
      var below = tickets.filter(function (k) { return k.lane === l && (k.s === 'piled' || (k.s === 'fall' && k.y > geo.gate)); });
      below.sort(function (a, b) { return a.y - b.y; });
      below.forEach(function (k, n) { k.s = 'sweep'; k.wait = n * 0.055; if (instant || reduce) catchIt(k); });
      l.pile = [];
      say(l.def.name + ' is on the job. It catches every ' + l.def.what + ' from here.');
    } else {
      say(l.def.name + ' is off. That trouble lands on your desk again.');
      if (done) { done = false; consoleEl.classList.remove('done'); }
    }
    consoleEl.classList.remove('nudge');
    refresh();
  }

  /* ---------- loop ---------- */
  function step(dt) {
    if (!done) t += dt;
    spawnIn -= dt;
    if (spawnIn <= 0) {
      spawn();
      /* open with a quick burst so trouble is visibly piling within a few seconds, then keep a lively cadence */
      spawnIn = done ? 1.5 : (reduce ? 1.3 : (burst-- > 0 ? 0.16 : Math.max(0.24, 0.5 - t * 0.03)));
    }
    for (var n = tickets.length - 1; n >= 0; n--) {
      var k = tickets[n], l = k.lane;
      if (k.s === 'fall') {
        var before = k.y;
        k.y += k.v * dt;
        if (l.on && before <= geo.gate && k.y >= geo.gate - geo.th * 0.5) { k.y = geo.gate - geo.th * 0.5; place(k); catchIt(k); continue; }
        if (!l.on || before > geo.gate) {
          var dest = slotY(l.pile.length);
          if (k.y >= dest) { land(k); continue; }
        }
        place(k);
      } else if (k.s === 'sweep') {
        if (k.wait > 0) { k.wait -= dt; continue; }
        k.y -= 760 * dt; k.rot *= 0.8;
        if (k.y <= geo.gate) { k.y = geo.gate; place(k); catchIt(k); continue; }
        place(k);
      }
    }
    refresh();
  }

  function refresh() {
    consoleEl.setAttribute('data-frames', frames);
    var d = deskCount();
    var mins = 8 * 60 + Math.floor(t * 2.2);
    elClock.textContent = Math.floor(mins / 60) + ':' + ('0' + (mins % 60)).slice(-2);
    setNum(elDesk, d); setNum(elCaught, caught); setNum(elHand, hand);
    var anyOn = lanes.some(function (l) { return l.on; });
    lanes.forEach(function (l) { l.el.classList.toggle('full', !l.on && l.pile.length >= geo.max); });
    if (!anyOn && d >= 9 && !done) { consoleEl.classList.add('nudge'); say('It does not stop, and the desk is filling. Flip a switch.'); }
    if (!done && allOn() && d === 0 && !tickets.some(function (k) { return k.s === 'sweep'; })) finish();
  }

  function finish() {
    done = true;
    consoleEl.classList.add('done'); consoleEl.classList.remove('nudge');
    say('Quiet. All five are on the job, and the desk is clear.');
    if (tape && tape.hidden) {
      tape.hidden = false;
      if (!instant && !reduce && !st && tape.scrollIntoView) setTimeout(function () { tape.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, 250);
    }
  }

  function frame(now) {
    raf = 0;
    if (!running) return;
    frames++;
    if (!last) last = now;
    /* advance in small sub-steps so a slow or throttled frame rate does not slow the morning down */
    var left = Math.max(0, Math.min(0.3, (now - last) / 1000)); last = now;
    while (left > 0.0005) { var dt = Math.min(0.05, left); step(dt); left -= dt; }
    raf = requestAnimationFrame(frame);
  }
  function sync() {
    var should = !userPaused && visible && !document.hidden;
    consoleEl.setAttribute('data-loop', (should ? 'run' : 'idle') + (visible ? '' : ' offscreen') + (document.hidden ? ' hidden' : ''));
    if (should && !running) { running = true; last = 0; raf = requestAnimationFrame(frame); }
    else if (!should && running) { running = false; if (raf) cancelAnimationFrame(raf); raf = 0; }
  }
  function fastForward(sec) { instant = true; for (var s = 0; s < sec; s += 0.05) step(0.05); instant = false; }

  function reset() {
    tickets.slice().forEach(remove);
    lanes.forEach(function (l) {
      l.pile = []; l.caught = 0; l.gateN.textContent = '0'; l.on = false;
      l.el.classList.remove('on'); l.sw.setAttribute('aria-checked', 'false'); l.state.textContent = 'off';
    });
    t = 0; spawnIn = 0.12; burst = 8; caught = 0; hand = 0; done = false;
    consoleEl.classList.remove('done', 'nudge');
    if (tape) tape.hidden = true;
    say('Flip a switch to put a system on the job, or press a pile to clear one by hand.');
    refresh();
    /* calm version: start with a little trouble already on the desk, so the board reads at a glance */
    if (reduce && st !== 'mid' && st !== 'done') fastForward(6);
    /* motion version: a few are already down when the visitor arrives, and more follow at once */
    else if (!reduce && !st) { fastForward(0.9); burst = 6; }
  }

  /* ---------- wiring ---------- */
  lanes.forEach(function (l) {
    l.sw.addEventListener('click', function () { toggle(l, !l.on); });
    l.pileBtn.addEventListener('click', function () { clearByHand(l); });
  });
  btnPause.addEventListener('click', function () {
    userPaused = !userPaused; btnPause.textContent = userPaused ? 'Resume' : 'Pause'; sync();
  });
  document.getElementById('g-reset').addEventListener('click', function () {
    reset(); if (userPaused) { userPaused = false; btnPause.textContent = 'Pause'; } sync();
  });
  document.addEventListener('ea-motion', function (e) {
    var nowReduce = !(e.detail && e.detail.on);
    if (nowReduce === reduce) return;
    reduce = nowReduce;
    reset(); if (userPaused) { userPaused = false; btnPause.textContent = 'Pause'; } sync();
  });
  document.addEventListener('visibilitychange', sync);
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (es) { visible = es[0].isIntersecting; sync(); }, { threshold: 0.05 }).observe(consoleEl);
  }
  var rz = 0;
  window.addEventListener('resize', function () { clearTimeout(rz); rz = setTimeout(measure, 120); });

  measure();
  reset();

  /* screenshot hook (see site.js): jump to a named state */
  document.addEventListener('ea-state', function (e) {
    st = e.detail && e.detail.state;
    if (st !== 'mid' && st !== 'done' && st !== 'first') return;
    reset();
    if (st === 'mid') { fastForward(13); toggle(lanes[0], true); toggle(lanes[3], true); fastForward(1.5); }
    if (st === 'done') { fastForward(6); lanes.forEach(function (l) { toggle(l, true); }); fastForward(2); refresh(); }
    userPaused = true; btnPause.textContent = 'Resume'; sync();
  });
  sync();
})();
