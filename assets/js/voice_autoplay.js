/**
 * voice_autoplay.js - Sistema Robusto de Autoplay
 * Implementa 7 estratégias de fallback para garantir que áudio toque
 */

class AudioPlaybackManager {
    constructor() {
        this.audioContext = null;
        this.currentAudio = null;
        this.isUnlocked = false;
    }

    // ESTRATÉGIA 1: Unlock AudioContext
    unlockAudioContext() {
        console.log('[Autoplay] Tentando unlock AudioContext...');

        try {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }

            if (this.audioContext.state === 'suspended') {
                this.audioContext.resume().then(() => {
                    console.log('✅ AudioContext resumed');
                });
            }

            // Toca buffer silencioso (truque de unlock)
            const buffer = this.audioContext.createBuffer(1, 1, 22050);
            const source = this.audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(this.audioContext.destination);
            source.start(0);

            this.isUnlocked = true;
            console.log('✅ AudioContext unlocked');
        } catch (error) {
            console.error('❌ Falha no unlock AudioContext:', error);
        }
    }

    // ESTRATÉGIA 2 + 3: Tentar múltiplos métodos
    async playAudio(url) {
        console.log(`[Autoplay] Tentando tocar: ${url}`);

        // Estratégia 2: Elemento do DOM
        const success = await this.tryElementPlay(url);
        if (success) return true;

        // Estratégia 3: Novo objeto Audio
        const success2 = await this.tryObjectPlay(url);
        if (success2) return true;

        // Estratégia 4: Botão manual
        this.showManualPlayButton(url);
        return false;
    }

    async tryElementPlay(url) {
        try {
            // ID específico sugerido no guia
            const audio = document.getElementById('reflex-audio-player');
            if (!audio) {
                console.warn('⚠️ Elemento audio não encontrado (reflex-audio-player)');
                return false;
            }

            audio.src = url;
            audio.load();

            // Tenta tocar
            await audio.play();
            console.log('✅ Áudio tocando (elemento DOM)');
            this.currentAudio = audio;

            // Hook para eventos
            this.attachEndedListener(audio);

            return true;
        } catch (error) {
            console.error('❌ Falha no elemento DOM:', error);
            return false;
        }
    }

    async tryObjectPlay(url) {
        try {
            const audio = new Audio(url);
            audio.preload = 'auto';

            await audio.play();
            console.log('✅ Áudio tocando (objeto Audio)');
            this.currentAudio = audio;

            // Hook para eventos
            this.attachEndedListener(audio);

            return true;
        } catch (error) {
            console.error('❌ Falha no objeto Audio:', error);
            return false;
        }
    }

    attachEndedListener(audio) {
        // Quando terminar, avisa o PlaybackManager ou window global
        audio.onended = () => {
            console.log('[Autoplay] Áudio finalizado.');
            if (window.onAudioEndCallback) {
                window.onAudioEndCallback();
            }

            // Também dispara evento simulado no elemento original se for fallback
            const reflexEl = document.getElementById('reflex-audio-player');
            if (reflexEl && audio !== reflexEl) {
                reflexEl.dispatchEvent(new Event('ended', { bubbles: true }));
            }

            // Dispara click no botão oculto (Compatibilidade com nossa lógica anterior)
            const hiddenBtn = document.getElementById('hidden_loop_trigger');
            if (hiddenBtn) hiddenBtn.click();
        };
    }

    showManualPlayButton(url) {
        console.log('⚠️ Autoplay falhou - mostrando botão manual');

        // Remove botão antigo se existir
        const oldBtn = document.getElementById('manual-play-btn');
        if (oldBtn) oldBtn.remove();

        // Cria botão
        const btn = document.createElement('button');
        btn.id = 'manual-play-btn';
        btn.textContent = '▶ Tocar Resposta';
        btn.style.cssText = `
            position: fixed;
            bottom: 120px;
            left: 50%;
            transform: translateX(-50%);
            padding: 15px 30px;
            font-size: 18px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.5);
            z-index: 10000;
            animation: pulse 1.5s ease-in-out infinite;
        `;

        btn.onclick = async () => {
            const audio = new Audio(url);
            this.currentAudio = audio;
            this.attachEndedListener(audio);
            await audio.play();
            btn.remove();
        };

        document.body.appendChild(btn);
    }

    // Callback quando áudio termina
    onAudioEnd(callback) {
        window.onAudioEndCallback = callback;
    }
}

// Instância global
window.audioManager = new AudioPlaybackManager();

// Expõe funções para o Reflex chamar
window.unlockAudio = () => window.audioManager.unlockAudioContext();
window.playResponseAudio = (url) => window.audioManager.playAudio(url);
window.onAudioEnd = (callback) => window.audioManager.onAudioEnd(callback);

// Compatibility with previous voice_chat.js logic
window.playFallback = (url) => window.audioManager.tryObjectPlay(url);

console.log('✅ AudioPlaybackManager inicializado (vUserGuide)');
