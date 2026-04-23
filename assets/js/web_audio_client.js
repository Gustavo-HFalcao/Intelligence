/**
 * Web Audio API + Web Speech API Client
 * Handles AudioContext, Autoplay, and Speech Recognition.
 */

// Global State
window.audioContext = null;
window.audioQueue = [];
window.isPlaying = false;
window.currentSource = null;
window.recognition = null;

/**
 * Initializes the AudioContext.
 * Must be called from a user gesture (click).
 */
window.initAudioSystem = function () {
    if (!window.audioContext) {
        try {
            window.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            console.log("AudioContext initialized.");
        } catch (e) {
            console.error("Web Audio API not supported:", e);
        }
    }

    if (window.audioContext.state === 'suspended') {
        window.audioContext.resume().then(() => {
            console.log("AudioContext resumed successfully.");
        });
    }
};

/**
 * Adds base64 audio to queue and attempts to play.
 * @param {string} audioBase64 - The audio data in base64.
 */
window.addToAudioQueue = function (audioBase64) {
    window.audioQueue.push(audioBase64);
    window.processAudioQueue();
};

/**
 * Processes the audio queue.
 */
window.processAudioQueue = async function () {
    if (window.audioQueue.length > 0 && !window.isPlaying) {
        window.isPlaying = true;

        // Ensure context is running
        if (window.audioContext && window.audioContext.state === 'suspended') {
            window.audioContext.resume();
        }

        const audioData = window.audioQueue.shift();

        try {
            // Decode base64
            const binaryString = atob(audioData);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            // Decode Audio Data
            const audioBuffer = await window.audioContext.decodeAudioData(bytes.buffer);

            // Create Buffer Source
            const source = window.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(window.audioContext.destination);

            source.onended = function () {
                window.isPlaying = false;
                window.currentSource = null;
                // Check for next item
                window.processAudioQueue();
            };

            window.currentSource = source;
            source.start(0);

        } catch (error) {
            console.error('Error playing audio:', error);
            window.isPlaying = false;
            window.processAudioQueue(); // Skip execution
        }
    }
};

/**
 * Stops current playback and clears queue.
 */
window.stopCurrentAudio = function () {
    if (window.currentSource) {
        try {
            window.currentSource.stop();
        } catch (e) { console.warn(e); }
        window.currentSource = null;
    }
    window.audioQueue = [];
    window.isPlaying = false;
};

/**
 * Starts Speech Recognition.
 */
window.startRecording = function () {
    // 1. Initialize logic if needed
    if (!window.recognition) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert("Seu navegador não suporta reconhecimento de voz.");
            return;
        }

        window.recognition = new SpeechRecognition();
        window.recognition.lang = 'pt-BR';
        window.recognition.continuous = false;
        window.recognition.interimResults = false; // Only final for simplicity

        window.recognition.onresult = function (event) {
            const transcript = event.results[0][0].transcript;

            // Send to Reflex
            const hiddenInput = document.getElementById("transcription_hidden_input");
            if (hiddenInput) {
                // React-friendly update
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                setter.call(hiddenInput, transcript);
                hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
                hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        };

        window.recognition.onerror = function (event) {
            console.error("Speech Recognition Error:", event.error);
        };

        window.recognition.onend = function () {
            // Optional: Auto-restart logic could go here
        };
    }

    // 2. Start
    try {
        window.recognition.start();
    } catch (e) {
        console.warn("Recognition already started or busy.");
    }
};
