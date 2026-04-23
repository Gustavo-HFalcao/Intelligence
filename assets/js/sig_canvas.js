/**
 * sig_canvas.js — Signature canvas binding for RDO form.
 * Loaded via rx.script (injected into <head>), persists across SPA navigation.
 * Uses WeakMap for per-node dedup so rebind happens correctly on canvas recreation.
 */
(function () {
  var _bound = new WeakMap();
  var _obs = null;
  var _timer = null;

  function _bind() {
    var c = document.getElementById('sig-canvas');
    if (!c) return;

    // Already bound to THIS exact DOM node? skip
    if (_bound.get(c)) return;
    _bound.set(c, true);

    var ctx = c.getContext('2d');
    ctx.strokeStyle = '#C98B2A';
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    var drawing = false;

    function getPos(e) {
      var r = c.getBoundingClientRect();
      var src = e.touches ? e.touches[0] : e;
      return {
        x: (src.clientX - r.left) * (c.width / r.width),
        y: (src.clientY - r.top) * (c.height / r.height)
      };
    }

    c.onmousedown = function (e) {
      e.preventDefault();
      drawing = true;
      var p = getPos(e);
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
    };
    c.onmousemove = function (e) {
      if (!drawing) return;
      var p = getPos(e);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
    };
    c.onmouseup = function () { drawing = false; };
    c.onmouseleave = function () { drawing = false; };

    c.ontouchstart = function (e) {
      e.preventDefault();
      drawing = true;
      var p = getPos(e);
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
    };
    c.ontouchmove = function (e) {
      e.preventDefault();
      if (!drawing) return;
      var p = getPos(e);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
    };
    c.ontouchend = function () { drawing = false; };
  }

  function _tryBind() {
    clearTimeout(_timer);
    _timer = setTimeout(_bind, 60);
  }

  // Expose globally so Reflex can trigger rebind via rx.call_script.
  // Force=true clears the WeakMap entry first so React-reused DOM nodes get rebound.
  window.sigCanvasRebind = function(force) {
    if (force) {
      var c = document.getElementById('sig-canvas');
      if (c) _bound.delete(c);
    }
    _bind();
  };

  // Start observer as soon as DOM is ready
  function _start() {
    _bind();
    [100, 250, 500, 1000, 2000].forEach(function (ms) { setTimeout(_bind, ms); });

    if (_obs) { _obs.disconnect(); }
    _obs = new MutationObserver(_tryBind);
    _obs.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _start);
  } else {
    _start();
  }
})();
