#!/bin/sh
# 把 Let's Encrypt 证书拷进 compose volume nginx_certs，然后重启 nginx。
# 用法（Linux 服务器，证书已由 certbot 签好）：
#   CERT_DIR=/etc/letsencrypt/live/your.domain ./scripts/load-le-certs.sh
set -e
CERT_DIR="${CERT_DIR:?set CERT_DIR to letsencrypt live directory}"
PROJ="${COMPOSE_PROJECT_NAME:-crm}"
VOL="${PROJ}_nginx_certs"
cid=$(docker run -d -v "$VOL:/certs" alpine:3.20 sleep 30)
docker cp "$CERT_DIR/fullchain.pem" "$cid:/certs/fullchain.pem"
docker cp "$CERT_DIR/privkey.pem" "$cid:/certs/privkey.pem"
docker rm -f "$cid" >/dev/null
docker compose restart nginx
echo "loaded certs from $CERT_DIR into $VOL"
