import reflex as rx
from datetime import datetime
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState
from bomtempo.core.supabase_client import sb_select, sb_update
from bomtempo.core.auth_utils import hash_password

class ResetPasswordState(GlobalState):
    reset_token: str = ""
    new_password: str = ""
    confirm_password: str = ""
    reset_error: str = ""
    reset_success: bool = False
    is_valid_token: bool = False
    is_loading_token: bool = True
    user_id_to_reset: str = ""

    async def load_page(self):
        """Runs on_load to verify the token from URL."""
        self.reset_error = ""
        self.reset_success = False
        self.is_loading_token = True
        
        # Get token from URL
        self.reset_token = self.router.query_params.get("token", "")
        
        if not self.reset_token:
            self.reset_error = "Token inválido ou ausente."
            self.is_valid_token = False
            self.is_loading_token = False
            return

        try:
            # Check token in DB
            res = sb_select("password_reset_tokens", filters={"token": self.reset_token}, limit=1)
            if not res:
                self.reset_error = "Token de redefinição não encontrado."
                self.is_valid_token = False
            else:
                token_data = res[0]
                expires_at = datetime.fromisoformat(token_data["expires_at"])
                
                if token_data["used"]:
                    self.reset_error = "Este token já foi utilizado."
                    self.is_valid_token = False
                elif expires_at < datetime.now():
                    self.reset_error = "Este token expirou."
                    self.is_valid_token = False
                else:
                    self.is_valid_token = True
                    self.user_id_to_reset = token_data["user_id"]
        except Exception as e:
            self.reset_error = "Erro ao validar token."
            self.is_valid_token = False
            
        self.is_loading_token = False

    async def handle_reset(self):
        if not self.new_password:
            self.reset_error = "Digite a nova senha."
            return
        if self.new_password != self.confirm_password:
            self.reset_error = "As senhas não coincidem."
            return
        if len(self.new_password) < 6:
            self.reset_error = "A senha deve ter pelo menos 6 caracteres."
            return

        try:
            hashed = hash_password(self.new_password)
            
            # Update user password
            sb_update("login", {"id": self.user_id_to_reset}, {"password": hashed})
            
            # Mark token as used
            sb_update("password_reset_tokens", {"token": self.reset_token}, {"used": True})
            
            self.reset_success = True
            self.reset_error = ""
            
        except Exception as e:
            self.reset_error = f"Erro ao atualizar senha: {e}"

def reset_password_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.image(src="/banner.png", width="150px", margin_bottom="20px"),
            rx.cond(
                ResetPasswordState.is_loading_token,
                rx.vstack(
                    rx.spinner(size="3", color=S.COPPER),
                    rx.text("Validando token...", color=S.TEXT_MUTED),
                    align="center",
                ),
                rx.cond(
                    ResetPasswordState.reset_success,
                    rx.vstack(
                        rx.icon(tag="circle-check", size=48, color=S.PATINA),
                        rx.heading("Senha Alterada!", color="white", size="7"),
                        rx.text("Sua senha foi atualizada com sucesso.", color=S.TEXT_MUTED),
                        rx.button(
                            "Ir para o Login",
                            on_click=rx.redirect("/"),
                            bg=S.COPPER,
                            color="#000",
                            margin_top="16px",
                        ),
                        align="center",
                        spacing="4",
                    ),
                    rx.vstack(
                        rx.heading("Redefinir Senha", color="white", size="7"),
                        rx.cond(
                            ResetPasswordState.is_valid_token,
                            rx.vstack(
                                rx.text("Digite sua nova senha de acesso.", color=S.TEXT_MUTED),
                                rx.input(
                                    placeholder="Nova senha",
                                    type="password",
                                    value=ResetPasswordState.new_password,
                                    on_change=ResetPasswordState.set_new_password,
                                    width="100%",
                                    bg="rgba(255,255,255,0.05)",
                                    border=f"1px solid {S.BORDER_SUBTLE}",
                                    color="white",
                                    height="48px",
                                ),
                                rx.input(
                                    placeholder="Confirme a nova senha",
                                    type="password",
                                    value=ResetPasswordState.confirm_password,
                                    on_change=ResetPasswordState.set_confirm_password,
                                    width="100%",
                                    bg="rgba(255,255,255,0.05)",
                                    border=f"1px solid {S.BORDER_SUBTLE}",
                                    color="white",
                                    height="48px",
                                ),
                                rx.cond(
                                    ResetPasswordState.reset_error != "",
                                    rx.text(ResetPasswordState.reset_error, color="#F87171", font_size="13px"),
                                ),
                                rx.button(
                                    "Atualizar Senha",
                                    on_click=ResetPasswordState.handle_reset,
                                    bg=S.COPPER,
                                    color="#000",
                                    width="100%",
                                    height="48px",
                                    margin_top="12px",
                                ),
                                width="100%",
                                spacing="4",
                            ),
                            rx.vstack(
                                rx.icon(tag="circle-x", size=48, color="#F87171"),
                                rx.text(ResetPasswordState.reset_error, color="#F87171", font_size="15px", font_weight="600"),
                                rx.button(
                                    "Voltar ao Login",
                                    on_click=rx.redirect("/"),
                                    variant="soft",
                                    color_scheme="gray",
                                    margin_top="10px",
                                ),
                                align="center",
                            )
                        ),
                        align="center",
                        spacing="6",
                    )
                )
            ),
            bg=S.BG_SURFACE,
            padding="48px",
            border_radius="16px",
            border=f"1px solid {S.BORDER_SUBTLE}",
            max_width="450px",
            width="90%",
            box_shadow=f"0 20px 50px -12px rgba(0,0,0,0.5)",
            class_name="glass-reveal",
        ),
        width="100%",
        height="100vh",
        bg=S.BG_VOID,
    )
