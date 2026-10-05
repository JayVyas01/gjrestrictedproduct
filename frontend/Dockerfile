# Web image for the offline demo stack: build the app, then serve it with Caddy (see Caddyfile).
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# vite.config.ts drops the mock service worker from dist; fail the build if it ever ships.
RUN npm run build && test ! -e dist/mockServiceWorker.js

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
# Run unprivileged: 8080 needs no root, and Caddy only writes its own /data and /config.
RUN addgroup -S web && adduser -S -G web web && chown -R web:web /data /config
USER web
EXPOSE 8080
