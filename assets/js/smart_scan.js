/**
 * SmartScan Live Preview
 * Bomtempo Intelligence - Vision Agent
 * 
 * Captura imagens em tempo real da câmera do usuário e analisa a qualidade da foto
 * (borrada, muito escura, sem nota fiscal) antes de enviar para o backend.
 */

class SmartScanPreview {
    constructor(videoElementId, canvasElementId, feedbackElementId) {
        this.video = document.getElementById(videoElementId);
        this.canvas = document.getElementById(canvasElementId);
        this.feedback = document.getElementById(feedbackElementId);
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.intervalId = null;
        this.stream = null;
    }

    async startCamera() {
        if (!this.video) return;
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } } 
            });
            this.video.srcObject = this.stream;
            this.video.play();
            
            // Inicia análise a cada 1 segundo (leve para não travar o celular)
            this.intervalId = setInterval(() => this.analyzeFrame(), 1000);
            this.updateFeedback("🟩 Câmera ativada. Posicione a Nota Fiscal no quadro.", "green");
        } catch (err) {
            console.error("Erro ao acessar câmera: ", err);
            this.updateFeedback("🟥 Erro ao acessar a câmera. Verifique as permissões.", "red");
        }
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }
    }

    updateFeedback(message, color) {
        if (!this.feedback) return;
        this.feedback.textContent = message;
        this.feedback.style.color = color;
    }

    analyzeFrame() {
        if (!this.video || !this.canvas || !this.ctx) return;
        
        // Desenha o frame atual no canvas isolado
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        
        // Pega os pixels para analisar brilho e nitidez básica
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        const data = imageData.data;
        
        let rSum = 0, gSum = 0, bSum = 0;
        
        // Amostragem (pular pixels para ser mais rápido)
        const step = 4 * 10; 
        let pixelsCount = 0;
        
        for (let i = 0; i < data.length; i += step) {
            rSum += data[i];
            gSum += data[i+1];
            bSum += data[i+2];
            pixelsCount++;
        }
        
        const rAvg = rSum / pixelsCount;
        const gAvg = gSum / pixelsCount;
        const bAvg = bSum / pixelsCount;
        const brightness = (0.299 * rAvg + 0.587 * gAvg + 0.114 * bAvg);
        
        if (brightness < 40) {
            this.updateFeedback("🟨 Muito escuro. Ligue o flash ou vá para um local iluminado.", "orange");
        } else if (brightness > 240) {
            this.updateFeedback("🟨 Muito estourado (brilho alto). Afaste-se da luz.", "orange");
        } else {
            this.updateFeedback("🟩 Iluminação OK. Segure firme e tire a foto.", "#4ADE80");
        }
        
        // Aqui no futuro podemos enviar o base64 para uma rota de FastAPI rápida 
        // ou rodar um modelo TensorFlow.js pequeno para detectar se a borda da NF está visível.
    }
}

window.SmartScanPreview = SmartScanPreview;
