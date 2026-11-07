#!/bin/sh
# Generates a self-signed certificate for localhost on first start.
# /etc/nginx/certs is a named volume, so the same cert is kept across `down` / `up`
# and a new one is made only after `down -v`. The private key never leaves the volume.
set -e

CERT_DIR=/etc/nginx/certs
CERT="$CERT_DIR/shop.crt"
KEY="$CERT_DIR/shop.key"

if [ -s "$CERT" ] && [ -s "$KEY" ]; then
  echo "15-generate-cert.sh: using existing certificate $CERT"
  exit 0
fi

echo "15-generate-cert.sh: generating self-signed certificate $CERT"
mkdir -p "$CERT_DIR"
openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 825 \
  -keyout "$KEY" -out "$CERT" \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
  -addext "basicConstraints=critical,CA:FALSE" \
  -addext "extendedKeyUsage=serverAuth"
chmod 600 "$KEY"
