/* Shared behaviour: the motion choice.
   <html> carries "motion" or "calm" (set in the head before first paint).
   The visitor's choice is remembered in localStorage and applies on every page.
   Nothing here depends on a query string. */
(function () {
  'use strict';
  var d = document.documentElement;
  var KEY = 'ea-motion';

  function isOn() { return d.classList.contains('motion'); }
  function apply(on) {
    d.classList.toggle('motion', on);
    d.classList.toggle('calm', !on);
    label();
    var ev;
    try { ev = new CustomEvent('ea-motion', { detail: { on: on } }); }
    catch (e) { ev = document.createEvent('CustomEvent'); ev.initCustomEvent('ea-motion', false, false, { on: on }); }
    document.dispatchEvent(ev);
  }
  function set(on, remember) {
    if (remember !== false) { try { localStorage.setItem(KEY, on ? 'on' : 'off'); } catch (e) { /* private mode: choice lasts for this page */ } }
    apply(on);
  }
  function label() {
    var on = isOn();
    Array.prototype.forEach.call(document.querySelectorAll('[data-motion-toggle]'), function (b) {
      b.hidden = false;
      b.textContent = on ? 'Reduce motion' : 'Play with motion';
    });
  }

  window.EA = { motion: isOn, setMotion: set };

  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-motion-toggle], [data-motion-on]') : null;
    if (!b) return;
    set(b.hasAttribute('data-motion-on') ? true : !isOn());
  });
  label();

  /* Screenshot hook for tools/shot.html: a parent frame may ask for a motion mode or a demo
     state. It changes nothing a visitor could not do by hand and stores nothing. */
  window.addEventListener('message', function (e) {
    if (location.protocol !== 'file:' && e.origin !== location.origin) return;   /* review tooling only */
    var m = e.data && e.data.ea;
    if (!m) return;
    if (m.motion === 'on' || m.motion === 'off') set(m.motion === 'on', false);
    if (m.state) {
      var ev;
      try { ev = new CustomEvent('ea-state', { detail: { state: String(m.state) } }); }
      catch (err) { return; }
      document.dispatchEvent(ev);
    }
  });
})();
