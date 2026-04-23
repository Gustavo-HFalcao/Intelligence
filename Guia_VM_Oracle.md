# Guia Prático: Configurando VM na Oracle Cloud (OCI)

Este guia contém os comandos exatos que você precisa rodar para preparar sua máquina.

## 1. Liberar Portas no Painel da Oracle (Obrigatório)
Antes de entrar na máquina, você precisa avisar a Oracle para deixar o tráfego passar:
1. Vá em **Networking** → **Virtual Cloud Networks**.
2. Clique na sua VNC e depois em **Security Lists**.
3. Clique em **Default Security List**.
4. Adicione **Ingress Rules**:
   - **Source CIDR:** `0.0.0.0/0`
   - **IP Protocol:** `TCP`
   - **Destination Port Range:** `80, 443` (HTTP e HTTPS).

---

## 2. Acessar a VM via SSH
No seu terminal (Windows PowerShell ou Termius):
```bash
ssh -i sua_chave.key ubuntu@SEU_IP_AQUI
```
*(Se usar Oracle Linux, o usuário é `opc`. Se usar Ubuntu, é `ubuntu`).*

---

## 3. Script de Preparação "Tudo-em-Um"
Copie e cole este comando para instalar Docker, Docker Compose e Nginx de uma vez:

```bash
sudo apt update && sudo apt upgrade -y && \
sudo apt install -y docker.io docker-compose nginx certbot python3-certbot-nginx git curl && \
sudo usermod -aG docker $USER && \
sudo systemctl enable --now docker nginx
```

> [!IMPORTANT]
> Após rodar o comando acima, deslogue da VM (`exit`) e logue novamente para que as permissões do Docker funcionem.

---

## 4. Firewall Interno da VM
A Oracle tem um firewall dentro do sistema também. Rode isso para liberar as portas definitivamente:

```bash
# Se for Ubuntu
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw --force enable

# Se por acaso for Oracle Linux (redhat-based)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

## 5. Como vamos subir o código?
Quando eu terminar oBackend e Frontend, faremos assim:
1. Você criará um repositório no GitHub (ou usará o atual).
2. Na VM, faremos `git clone`.
3. Rodaremos `docker-compose up -d`.

---

## 6. HTTPS (SSL Grátis)
Quando você tiver um domínio apontado para o IP da VM, rode apenas este comando:
```bash
sudo certbot --nginx -d seu-dominio.com
```

---

### O que você pode fazer agora?
1. **Crie a conta** na Oracle Cloud.
2. **Suba a instância** (Dê preferência para **Ubuntu 22.04**).
3. **Siga o Passo 1** (Liberar portas no painel).
4. **Tente conectar** via SSH.
5. **Rode o Script do Passo 3**.

Se travar em qualquer parte, me mande o erro aqui!
