#!/bin/sh
set -e
mkdir -p /etc/nginx/certs
if [ ! -f /etc/nginx/certs/fullchain.pem ]; then
  apk add --no-cache openssl >/dev/null
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/certs/privkey.pem \
    -out /etc/nginx/certs/fullchain.pem \
    -subj "/CN=localhost"
fi
SUFFIX=""
if [ -n "${NGINX_HTTPS_PORT}" ] && [ "${NGINX_HTTPS_PORT}" != "443" ]; then
  SUFFIX=":${NGINX_HTTPS_PORT}"
fi
sed "s|__TLS_SUFFIX__|${SUFFIX}|g" /etc/nginx/nginx.conf.template > /tmp/nginx.conf
exec nginx -c /tmp/nginx.conf -g "daemon off;"
