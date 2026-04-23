/**
 * BOMTEMPO Voice Chat Logic
 * Supports Chrome, Edge, and Safari (via webkit prefix).
 */

console.log("Loading Voice Chat Module v3.0");

// Global recognition instance
window.recognition = null;

/**
 * Initializes and starts speech recognition.
 * Must be called directly from a user interaction (click) to work on Safari.
 */
window.startRecording = function () {
    console.log("Attempting to start recording...");

    // 1. Browser Compatibility Check
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert("Seu navegador não suporta reconhecimento de fala. Tente usar Chrome, Edge ou Safari atualizado.");
        return;
    }

    // 2. Initialize Recognition
    try {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        window.recognition = new SpeechRecognition();

        // Configuration
        window.recognition.lang = 'pt-BR';
        window.recognition.continuous = false; // Stop after one sentence
        window.recognition.interimResults = false;

        // Event Handlers
        window.recognition.onstart = function () {
            console.log("Voice recognition started successfully.");
        };

        window.recognition.onresult = function (event) {
            const transcript = event.results[0][0].transcript;
            console.log("Transcript captured:", transcript);

            // Send to Reflex
            // 1. Try visible input first (Mobile/Desktop V2)
            const mainInput = document.getElementById("chat_main_input");
            const hiddenInput = document.getElementById("audio_hidden_id");

            // Helper to set value safely in React
            const setReactValue = (input, value) => {
                if (!input) return;
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                setter.call(input, value);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                input.dispatchEvent(new Event('blur', { bubbles: true }));
            }

            if (mainInput) {
                console.log("Updating visible input... (DISABLED per user request)");
                // setReactValue(mainInput, transcript);
            }

            /*
            // NEW STRATEGY: Direct API Call (DISABLED - Reverting to Reflex State)
            console.log("Calling Voice API for Audio Response...");

            fetch('/api/process_voice', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: transcript, mobile: true })
            })
            ...
            */


            // OLD LOGIC (RESTORED: Trigger Reflex State for Auto-Send)
            if (hiddenInput) {
                console.log("Triggering hidden input for Auto-Send via Reflex...");
                setReactValue(hiddenInput, transcript);
            }


            console.log("Events dispatched for transcript:", transcript);
        };

        window.recognition.onerror = function (event) {
            console.error("Recognition error:", event.error);
            if (event.error === 'not-allowed') {
                alert("Permissão de microfone negada. Verifique as configurações do navegador.");
            } else if (event.error === 'no-speech') {
                console.log("No speech detected.");
            } else {
                // On Safari, 'network' error can happen if offline
                alert("Erro no reconhecimento de voz: " + event.error);
            }
            // Ensure UI resets
            stopReflexRecordingState();
        };

        window.recognition.onend = function () {
            console.log("Recognition service disconnected.");
            // UI sync handled by on_change event in Reflex if successful
        };

        // 3. Start
        window.recognition.start();

    } catch (e) {
        console.error("Exception initializing speech recognition:", e);
        alert("Erro ao iniciar microfone: " + e.message);
    }
}

/**
 * Stops recognition manually
 */
window.stopRecording = function () {
    console.log("Stopping recording manually...");
    if (window.recognition) {
        window.recognition.stop();
    }
}

/**
 * Helper to force UI reset in case of errors
 */
function stopReflexRecordingState() {
    // Ideally we would trigger a python event here to set is_recording = False
    // For now we rely on the manual stop or the input change.
}

// SATARI FIX: Direct Event Listener
// Safari requires SpeechRecognition to start immediately on User Gesture (Click).
// Reflex's on_click creates a round-trip (Client -> Server -> Client) which acts as an async task,
// causing Safari to block the recognition start.
// Solution: Attach a direct JS listener to the button.
document.addEventListener('DOMContentLoaded', function () {
    console.log("Initializing Voice Chat Listeners...");

    // Function to attach listener
    function attachMicListener() {
        const micBtn = document.getElementById("mobile_mic_btn");
        if (micBtn) {
            console.log("Mobile Mic Button found. Attaching direct listener.");
            // Remove old listeners to avoid duplicates (clone node trick)
            const newBtn = micBtn.cloneNode(true);
            micBtn.parentNode.replaceChild(newBtn, micBtn);

            newBtn.addEventListener('click', function (e) {
                console.log("Mic clicked (Direct JS). Starting recognition immediately.");
                // Prevent Reflex default click if needed, but we want the visual state update too.
                // We'll let it bubble or just fire startRecording which is idempotent-ish.
                window.startRecording();
            });
        } else {
            // Reflex might re-render, so we might need to retry or use MutationObserver.
            // For now, retry a few times.
            setTimeout(attachMicListener, 1000);
        }
    }

    // Initial attempt
    setTimeout(attachMicListener, 1000);

    // Observer for dynamic updates (Reflex pages are SPAs)
    const observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            if (mutation.type === 'childList') {
                const micBtn = document.getElementById("mobile_mic_btn");
                if (micBtn && !micBtn.hasAttribute('data-voice-attached')) {
                    micBtn.setAttribute('data-voice-attached', 'true');
                    micBtn.addEventListener('click', function () {
                        console.log("Mic clicked (Observer).");
                        window.startRecording();
                    });
                }
            }
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });
});

/**
 * Validates availability for external calls
 */
window.initVoiceChat = function () {
    console.log("Voice Chat Initialized via Python call.");
    if (!window.recognition) {
        console.log("Recognition not pre-loaded, waiting for interaction.");
    }
}

/**
 * Clears the chat input field visually.
 * Called from Python after message send to ensure UI is clean.
 */
window.clearChatInput = function () {
    const mainInput = document.getElementById("chat_main_input");
    if (mainInput) {
        console.log("Clearing chat input via React-compatible setter...");

        // React overrides value setter, so we must access native prototype
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        nativeInputValueSetter.call(mainInput, "");

        // Dispatch events to trigger React change listeners
        mainInput.dispatchEvent(new Event('input', { bubbles: true }));
        mainInput.dispatchEvent(new Event('change', { bubbles: true }));

        // Also clear visually just in case
        mainInput.value = "";
    } else {
        console.warn("chat_main_input not found during clearChatInput call.");
    }
}

/**
 * Automatically scrolls a container to the bottom.
 * @param {string} id - The ID of the container element.
 */
window.scrollToBottom = function (id) {
    setTimeout(() => {
        const container = document.getElementById(id);
        if (container) {
            console.log("Scrolling container to bottom:", id);
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        } else {
            console.warn("scrollToBottom: Container not found:", id);
        }
    }, 100); // Small delay to allow React to render the new message
}

/**
 * Robust Audio Player & Autoplay Unlocker
 */

// Global Audio Context for unlocking (if needed)
window.audioCtx = null;

// Strategies for Autoplay
window.unlockAudio = function () {
    console.log("Unlocking Audio Engine...");

    // 1. Try to resume AudioContext if exists
    if (window.audioCtx && window.audioCtx.state === 'suspended') {
        window.audioCtx.resume();
    }

    // 2. Play silent sound on the main player to "bless" the element
    const p = document.getElementById("tts_audio_player");
    if (p) {
        // Playing empty or current trigger browser to accept future plays
        // We catch errors to avoid noise in console if src is empty
        p.play().then(() => p.pause()).catch(e => { });
    }
}

window.playResponseAudio = function (url) {
    console.log("Attempting to play audio: " + url);

    const p = document.getElementById("tts_audio_player");

    if (p) {
        // Strategy 1: Use the existing Reflex element (Best for preserving hooks)
        p.src = url;
        p.load();
        var playPromise = p.play();

        if (playPromise !== undefined) {
            playPromise
                .then(() => console.log("Strategy 1 (DOM Element) Success."))
                .catch(error => {
                    console.warn("Strategy 1 Failed:", error);
                    // Strategy 2: Fallback to new Audio object
                    console.log("Attempting Strategy 2 (New Audio Object)...");
                    playFallback(url);
                });
        }
    } else {
        console.warn("Player element not found! Using Strategy 2 directly.");
        playFallback(url);
    }
}

function playFallback(url) {
    try {
        const audio = new Audio(url);
        audio.onended = function () {
            console.log("Fallback Audio Ended.");

            // Strategy: Click the hidden Reflex button to trigger backend event
            const triggerBtn = document.getElementById("hidden_loop_trigger");
            if (triggerBtn) {
                console.log("Clicking hidden trigger button...");
                triggerBtn.click();
            } else {
                console.error("Critical: Hidden loop trigger button not found!");
            }
        };

        audio.play()
            .then(() => console.log("Strategy 2 Success."))
            .catch(e => console.error("Strategy 2 Failed (Final):", e));

    } catch (e) {
        console.error("Critical Audio Failure:", e);
    }
}
