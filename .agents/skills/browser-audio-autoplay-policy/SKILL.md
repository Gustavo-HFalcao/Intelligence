---
name: browser-audio-autoplay-policy
description: "Guidelines for bypassing strict browser Autoplay blocks when implementing AI TTS (Text-to-Speech) outputs in modern web apps."
---

# Browser Audio Autoplay Bypassing (TTS)

Modern browsers (Chrome, Safari, iOS) strictly block any `.play()` audio requests that are not *directly* and *synchronously* tied to a user interaction (like a click). Since AI agents take several seconds to generate a TTS response, the browser's "gesture token" expires, and the audio gets blocked silently in the console.

## 1. The "Unlock" Strategy (Silent Play)
Do not try to spawn a new `<audio>` element from the Python backend *after* the server responds. 
Instead, render a fixed, hidden `<audio id="agent-tts-player">` component on the page globally.

## 2. Synchronous Activation
On the EXACT moment the user clicks "Ask AI" or "Start Microphone", run a custom Javascript hook (`rx.call_script()`) that does this synchronously:
```javascript
const player = document.getElementById("agent-tts-player");
// Carrega um áudio mudo de 0.1 segundo base64
player.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA"; 
player.play().then(() => player.pause()).catch(e => console.log(e));
```
**Why?** This forces the browser to grant the "audio playing privilege" to this specific `<audio>` element because the initiation was tied to a physical user click.

## 3. The Async Playback
Minutes later, when the heavy AI Python task finishes and the Reflex backend returns the real `tts_file_url` dynamically, use `rx.call_script()` again to simply swap the `.src` of the *already unlocked* `agent-tts-player` and call `.play()`. The browser will allow it 100% of the time, even on strict Apple devices, because the element is already "authenticated".
