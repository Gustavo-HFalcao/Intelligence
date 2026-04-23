"""
Emergency Password Hash Generator — Bomtempo Dashboard
Generates a PBKDF2-HMAC-SHA256 hash string compatible with auth_utils.py.
Use this to manually reset a password via the Supabase SQL editor.
"""
import sys
import os

# Add project root to sys.path to import auth_utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from bomtempo.core.auth_utils import hash_password
except ImportError:
    print("Erro: Não foi possível importar auth_utils.")
    print("Certifique-se de rodar este script da raiz do projeto: python tools/emergency_password_reset.py")
    sys.exit(1)


def main():
    print("─" * 60)
    print("  Bomtempo — Gerador de Senha de Emergência (PBKDF2)")
    print("─" * 60)

    username = input("Usuário alvo (ex: gustavo): ").strip()
    if not username:
        print("Usuário não pode ser vazio.")
        return

    import getpass
    password = getpass.getpass("Nova senha (oculta): ").strip()
    if not password:
        print("Senha não pode ser vazia.")
        return

    confirm = getpass.getpass("Confirme a nova senha: ").strip()
    if password != confirm:
        print("Senhas não conferem. Operação cancelada.")
        return

    hashed = hash_password(password)

    # Determine which column to update
    # If your Supabase table uses 'pw_hash', use that; otherwise 'password'.
    print("\n✅ Hash gerado com sucesso.")
    print("\n[Cole no Supabase SQL Editor — escolha conforme seu schema]\n")
    print("-- Se a coluna se chama 'pw_hash':")
    print(f"UPDATE login SET pw_hash = '{hashed}' WHERE username = '{username}';")
    print("\n-- Se a coluna ainda se chama 'password':")
    print(f"UPDATE login SET password = '{hashed}' WHERE username = '{username}';")
    print("\n" + "─" * 60)
    print("ATENÇÃO: este hash é único (salt aleatório). Não reutilize em múltiplos usuários.")


if __name__ == "__main__":
    main()
