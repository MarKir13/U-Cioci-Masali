# HTTPS proxy in front of the shop: TLS with a self-signed cert, HTTP -> HTTPS redirect.
FROM nginx:1.28.0-alpine

# openssl generates the certificate on first start
RUN apk add --no-cache openssl

# The official image runs /docker-entrypoint.d/*.sh in name order before starting nginx:
# 15-generate-cert.sh runs before 20-envsubst-on-templates.sh, which renders the config below
# into /etc/nginx/conf.d/default.conf (only defined env vars such as ${HTTPS_PORT} are replaced).
COPY --chmod=755 15-generate-cert.sh /docker-entrypoint.d/15-generate-cert.sh
COPY default.conf.template /etc/nginx/templates/default.conf.template
