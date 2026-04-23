(function(){
  var _ctx = null;
  var _rec = null;
  var _unlocked = false;
  var _lastSrc = '';

  /* ── Phantom <audio> criado imediatamente no load ───────────────────────── */
  var _el = (function(){
    var ex = document.getElementById('_aai_audio');
    if(ex) return ex;
    var el = document.createElement('audio');
    el.id = '_aai_audio';
    el.preload = 'none';
    el.style.cssText = 'position:fixed;bottom:-9999px;left:-9999px;width:1px;height:1px;opacity:0.001;pointer-events:none';
    document.body.appendChild(el);
    return el;
  })();

  var SILENCE = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';

  function _doUnlock(){
    if(_unlocked) return;
    _el.src = SILENCE;
    _el.volume = 0.001;
    var p = _el.play();
    if(p && p.catch) p.catch(function(){});
    _el.onended = null;
    try{
      if(!_ctx) _ctx = new (window.AudioContext||window.webkitAudioContext)();
      if(_ctx.state==='suspended') _ctx.resume().catch(function(){});
    }catch(e){}
    _unlocked = true;
    console.log('[ActionAI] unlocked via gesture');
  }

  /* ── Event delegation: intercepta cliques nos botões AAI ANTES do WebSocket */
  document.addEventListener('click', function(e){
    var t = e.target;
    if(t && (
      t.closest('#_aai_fab') ||
      t.closest('#_aai_popup') ||
      t.id === '_aai_fab' ||
      t.id === '_aai_popup'
    )){
      _doUnlock();
    }
  }, true);

  /* ── API pública chamada pelo Reflex ─── */
  window.actionAIUnlockAudio = function(){ _doUnlock(); };

  /* ── Resolve URL ─────────────────────────────────────────────────────────── */
  function _resolveUrl(url){
    if(url && url.startsWith('/_upload/')){
      var loc = window.location;
      if(loc.port==='3000'||loc.port===''){
        return loc.protocol+'//'+loc.hostname+':8000/'+url.replace(/^\//,'');
      }
    }
    return url;
  }

  /* ── Play ────────────────────────────────────────────────────────────────── */
  window.actionAIPlayAudio = function(url){
    if(!url || !url.trim()) return;
    var src = _resolveUrl(url.trim());
    console.log('[ActionAI] play →', src);
    _el.pause();
    _el.currentTime = 0;
    _el.volume = 1.0;
    _el.src = src;
    _el.load();
    _el.onended = function(){ _lastSrc=''; if(window._aaiOnAudioEnded) window._aaiOnAudioEnded(); };
    _el.onerror = function(ev){ console.error('[ActionAI] audio error', ev.target&&ev.target.error); if(window._aaiOnAudioEnded) window._aaiOnAudioEnded(); };
    _el.play()
      .then(function(){ console.log('[ActionAI] playing OK'); })
      .catch(function(err){
        console.warn('[ActionAI] play() blocked:', err.name, '-', err.message, '| unlocked:', _unlocked);
        _playViaCtx(src);
      });
  };

  function _playViaCtx(url){
    if(!_ctx){ console.error('[ActionAI] no ctx'); if(window._aaiOnAudioEnded) window._aaiOnAudioEnded(); return; }
    if(_ctx.state==='suspended'){
      _ctx.resume().then(function(){ _fetchAndDecode(url); }).catch(function(){ if(window._aaiOnAudioEnded) window._aaiOnAudioEnded(); });
      return;
    }
    _fetchAndDecode(url);
  }

  function _fetchAndDecode(url){
    fetch(url)
      .then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.arrayBuffer(); })
      .then(function(ab){ return _ctx.decodeAudioData(ab); })
      .then(function(decoded){
        var src = _ctx.createBufferSource();
        src.buffer = decoded; src.connect(_ctx.destination);
        src.onended = function(){ _lastSrc=''; if(window._aaiOnAudioEnded) window._aaiOnAudioEnded(); };
        src.start(0);
        console.log('[ActionAI] AudioContext OK');
      })
      .catch(function(e){ console.error('[ActionAI] ctx fallback failed:', e); if(window._aaiOnAudioEnded) window._aaiOnAudioEnded(); });
  }

  /* ── MutationObserver: reage à mudança de tts_audio_src via WebSocket ───── */
  function _watchTtsSrc(){
    var span = document.getElementById('_aai_tts_src_span');
    if(!span){ setTimeout(_watchTtsSrc, 400); return; }
    new MutationObserver(function(){
      var src = (span.textContent||span.innerText||'').trim();
      if(src && src !== _lastSrc){
        _lastSrc = src;
        console.log('[ActionAI] observer → play:', src);
        window.actionAIPlayAudio(src);
      }
    }).observe(span, { childList:true, characterData:true, subtree:true });
    console.log('[ActionAI] observer pronto');
  }
  document.readyState==='loading'
    ? document.addEventListener('DOMContentLoaded', _watchTtsSrc)
    : _watchTtsSrc();

  /* ── Mic permission ─────────────────────────────────────────────────────── */
  window.actionAIRequestMicPermission = function(){
    if(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia)
      navigator.mediaDevices.getUserMedia({audio:true})
        .then(function(s){ s.getTracks().forEach(function(t){t.stop();}); })
        .catch(function(e){ console.warn('[ActionAI] mic denied:',e); });
  };

  /* ── Speech Recognition ─────────────────────────────────────────────────── */
  window.actionAIStartVoice = function(){
    var SR = window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR){ console.warn('[ActionAI] SR not supported'); if(window._aaiOnStopped) window._aaiOnStopped(); return; }
    if(_rec){ try{_rec.abort();}catch(e){} _rec=null; }
    _rec = new SR();
    _rec.continuous = false; _rec.lang = 'pt-BR';
    _rec.interimResults = false; _rec.maxAlternatives = 1;
    _rec.onresult = function(e){ if(window._aaiOnResult) window._aaiOnResult(e.results[0][0].transcript); };
    _rec.onend  = function(){ _rec=null; if(window._aaiOnStopped) window._aaiOnStopped(); };
    _rec.onerror= function(e){ console.warn('[ActionAI] SR error:',e.error); _rec=null; if(window._aaiOnStopped) window._aaiOnStopped(); };
    try{ _rec.start(); }catch(e){ console.warn('[ActionAI] rec.start() failed:',e); _rec=null; if(window._aaiOnStopped) window._aaiOnStopped(); }
  };
  window.actionAIStopVoice = function(){ if(_rec){ try{_rec.stop();}catch(e){} _rec=null; } };

  /* ── Hidden-input bridges (JS → Reflex) ─────────────────────────────────── */
  function _triggerInput(id, val){
    var el = document.getElementById(id);
    if(!el) return;
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(el, val);
    el.dispatchEvent(new Event('input',{bubbles:true}));
  }
  window._aaiOnResult     = function(t){ _triggerInput('_aai_transcript_input', t); };
  window._aaiOnStopped    = function(){ _triggerInput('_aai_stopped_input', String(Date.now())); };
  window._aaiOnAudioEnded = function(){ _triggerInput('_aai_audio_ended_input', String(Date.now())); };

})();
