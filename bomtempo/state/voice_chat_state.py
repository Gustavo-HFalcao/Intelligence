import json
from datetime import datetime

import reflex as rx

from bomtempo.core.ai_client import ai_client
from bomtempo.core.ai_context import AIContext
from bomtempo.core.ai_tools import AI_TOOLS, execute_tool
from bomtempo.core.data_loader import DataLoader
from bomtempo.core.supabase_client import sb_rpc

# from bomtempo.core.openai_service import get_openai_client # Deprecated for this use case


class VoiceChatState(rx.State):
    """
    Estado Simplificado: Push-to-Talk (Transcrever + Chat apenas)
    Sem TTS / Sem Autoplay Handsfree (Removido por limitação de navegador)
    """

    # Chat State
    messages: list[dict] = []
    is_listening: bool = False  # Se Web Speech API está ouvindo
    is_processing: bool = False  # Se está gerando resposta da AI

    # Debug Legend
    debug_logs: list[str] = []

    def add_log(self, message: str):
        """Log visual"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.debug_logs.insert(0, f"[{timestamp}] {message}")
        if len(self.debug_logs) > 20:
            self.debug_logs.pop()

    def start_listening(self):
        """Ativa microfone via JS (Interaction One-Shot: Limpa histórico)"""
        self.messages = []  # Limpa o chat anterior
        self.is_listening = True
        self.add_log("Ouvindo...")
        return rx.call_script("""
            window.SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (window.SpeechRecognition) {
                if (!window.recognition) {
                    window.recognition = new window.SpeechRecognition();
                    window.recognition.continuous = false;
                    window.recognition.lang = 'pt-BR';
                    window.recognition.interimResults = false;
                    
                    window.recognition.onend = () => {
                        const input = document.getElementById('voice_status_input');
                        if(input) {
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            setter.call(input, "stopped");
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    };

                    window.recognition.onresult = (event) => {
                        const transcript = event.results[0][0].transcript;
                        const input = document.getElementById('voice_transcript_input');
                        if (input) {
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            setter.call(input, transcript);
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    };
                }
                window.recognition.start();
            } else {
                alert("Navegador não suporta reconhecimento de voz.");
            }
        """)

    def stop_listening(self):
        """Para microfone via JS"""
        self.is_listening = False
        self.add_log("Parando microfone...")
        return rx.call_script("if(window.recognition) window.recognition.stop();")

    def on_voice_status_change(self, status: str):
        """Callback do JS quando reconhecimento para"""
        if status == "stopped":
            self.is_listening = False

    def process_transcript(self, text: str):
        """Recebe texto transcrito — atualiza UI e dispara o loop agêntico em background."""
        if not text:
            return
        self.is_listening = False
        self.is_processing = True
        self.add_log(f"Usuário: {text}")
        self.messages.append({"role": "user", "content": text})
        yield VoiceChatState.run_agentic_loop

    @rx.event(background=True)
    async def run_agentic_loop(self):
        """Loop agêntico em background — não bloqueia o event loop."""
        try:
            system_prompt = AIContext.get_system_prompt(is_mobile=False)
            schema_context = sb_rpc("get_schema_context")

            async with self:
                recent_history = list(self.messages[-6:])

            context_messages = [
                {
                    "role": "system",
                    "content": f"{system_prompt}\n\nSCHEMA DISPONÍVEL:\n{schema_context}",
                }
            ]
            context_messages.extend(recent_history)

            max_iterations = 5
            for i in range(max_iterations):
                response = ai_client.query_agentic(context_messages, tools=AI_TOOLS, force_tool=(i == 0))

                if isinstance(response, str):
                    async with self:
                        self.add_log(f"AI: {response[:30]}...")
                        self.messages.append({"role": "assistant", "content": response})
                        self.is_processing = False
                    break

                tool_calls = response.tool_calls
                context_messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                for tool_call in tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    async with self:
                        self.add_log(f"Consultando: {name}...")

                    result = execute_tool(name, args)

                    context_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": result,
                    })
            else:
                async with self:
                    self.messages.append({"role": "assistant", "content": "Não consegui concluir. Tente reformular."})
                    self.is_processing = False

        except Exception as e:
            async with self:
                self.add_log(f"Erro: {str(e)}")
                self.messages.append({"role": "assistant", "content": "Desculpe, erro ao acessar os dados."})
                self.is_processing = False
