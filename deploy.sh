#!/bin/bash
# deploy.sh — Pull + rebuild na VM Google Cloud
# Uso: ./deploy.sh
set -e

echo "=== Bomtempo Intelligence — Deploy ==="

# Pull do código novo
git pull origin main

# Rebuild e restart sem downtime prolongado
docker compose build --no-cache
docker compose up -d --force-recreate

# Limpa imagens antigas
docker image prune -f

echo ""
echo "✓ Deploy concluído!"
echo "  Acesse: http://$(curl -s ifconfig.me):8080"
