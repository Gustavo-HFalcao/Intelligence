/**
 * Voice Handler - Handsfree Chat
 * Baseado em: MDN Web Audio API + Web Speech API
 * Refs: 
 * - https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API
 * - https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition
 */

window.VoiceHandler = {
    audioContext: null,
    recognition: null,
    audioQueue: [],
    isPlaying: false,
    isListening: false,

    /**
     * Helper para log e event dispatch
     */
    log: function (message) {
        console.log(`[VoiceHandler] ${message}`);
        window.dispatchEvent(new CustomEvent('voiceLog', {
            detail: { message: message }
        }));
    },

    /**
     * Inicializa sistema de áudio
     * Deve ser chamado após interação do usuário
     */
    init: function () {
        this.log("Inicializando Audio Context...");

        try {
            // Criar AudioContext (padrão MDN)
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContext();

            // Resume se suspenso (política de autoplay)
            if (this.audioContext.state === 'suspended') {
                this.audioContext.resume().then(() => {
                    this.log("AudioContext Resumed (Autoplay unlocked)");
                });
            }

            // Configurar Web Speech API
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            if (SpeechRecognition) {
                this.recognition = new SpeechRecognition();
                this.recognition.continuous = false;
                this.recognition.interimResults = true;
                this.recognition.lang = 'pt-BR';

                // Callbacks
                this.recognition.onresult = this.onSpeechResult.bind(this);
                this.recognition.onerror = this.onSpeechError.bind(this);
                this.recognition.onend = this.onSpeechEnd.bind(this);
                this.recognition.onstart = () => this.log("SpeechRecognition Started (Listening...)");

                this.log("SpeechRecognition Configured.");
            } else {
                this.log("ERRO: Web Speech API não suportada neste navegador.");
            }

            this.log("VoiceHandler inicializado com sucesso.");
            return true;
        } catch (e) {
            this.log(`ERRO CRÍTICO na inicialização: ${e.message}`);
            return false;
        }
    },

    /**
     * Inicia captura de voz
     */
    startListening: function () {
        if (!this.recognition) {
            this.log('Tentativa de iniciar mas SpeechRecognition não existe.');
            return false;
        }

        if (this.isListening) {
            this.log('Já está ouvindo.');
            return true;
        }

        try {
            this.log('Solicitando start no SpeechRecognition...');
            this.recognition.start();
            this.isListening = true;
            document.dispatchEvent(new CustomEvent('voiceListeningStarted'));
            return true;
        } catch (error) {
            this.log(`Erro ao iniciar gravação: ${error.message || error}`);
            if (error.name === 'InvalidStateError') {
                this.isListening = true;
            }
            return false;
        }
    },

    /**
     * Para captura de voz
     */
    stopListening: function () {
        this.log('Parando escuta...');
        if (this.recognition && this.isListening) {
            this.recognition.stop();
            this.isListening = false;
        }
    },

    /**
     * Callback quando reconhecimento retorna resultado
     */
    onSpeechResult: function (event) {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = 0; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;

            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }

        if (interimTranscript) {
            // Opcional: Logar interim apenas se quiser muito detalhe
            // this.log(`Interim: ${interimTranscript}`);
        }

        if (finalTranscript) {
            this.log(`Transcript Final detectado: "${finalTranscript}"`);
            const customEvent = new CustomEvent('voiceFinal', {
                detail: { text: finalTranscript }
            });
            window.dispatchEvent(customEvent);
        }
    },

    /**
     * Tratamento de erros
     */
    onSpeechError: function (event) {
        this.log(`Erro SpeechRecognition: ${event.error}`);
        if (event.error !== 'no-speech') {
            this.isListening = false;
            window.dispatchEvent(new CustomEvent('voiceError', {
                detail: { error: event.error }
            }));
        }
    },

    /**
     * Quando reconhecimento termina
     */
    onSpeechEnd: function () {
        this.log('SpeechRecognition terminou (silêncio ou stop).');
        this.isListening = false;
        window.dispatchEvent(new CustomEvent('voiceListeningStopped'));
    },

    /**
     * Adiciona áudio à fila e toca automaticamente
     * @param {string} audioBase64 - Áudio em base64
     */
    playAudio: async function (audioBase64) {
        this.log(`Adicionando áudio à fila (Tamanho: ${audioBase64.length})`);
        this.audioQueue.push(audioBase64);

        if (!this.isPlaying) {
            await this.playNext();
        }
    },

    /**
     * Toca próximo áudio da fila
     */
    playNext: async function () {
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            window.dispatchEvent(new CustomEvent('audioQueueEmpty'));
            return;
        }

        this.isPlaying = true;
        const audioBase64 = this.audioQueue.shift();

        try {
            // Decodificar base64 para ArrayBuffer (padrão MDN)
            const binaryString = atob(audioBase64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            // Decodificar áudio (Web Audio API)
            const audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer);

            // Criar source e conectar
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioContext.destination);

            // Quando terminar, tocar próximo
            source.onended = () => {
                this.playNext();
            };

            // Tocar
            source.start(0);
            window.dispatchEvent(new CustomEvent('audioPlaying'));

        } catch (error) {
            console.error('Erro ao tocar áudio:', error);
            this.isPlaying = false;
            this.playNext(); // Tentar próximo
        }
    },

    /**
     * Para reprodução atual, limpa fila e reinicia AudioContext se necessário
     */
    stopAudio: function () {
        this.audioQueue = []; // Limpa fila

        if (this.audioContext) {
            this.audioContext.suspend().then(() => {
                this.audioContext.resume();
            }); // Hack rápido para parar sons atuais
        }
        this.isPlaying = false;
    }
};
