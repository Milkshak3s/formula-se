# --- build stage ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# --- serve stage (Caddy serves the SPA and proxies /api to the api service) ---
FROM caddy:2-alpine
# The upstream binary ships with cap_net_bind_service file capabilities (for
# binding :80/:443). We listen on the unprivileged :8080, and under a hardened
# securityContext (allowPrivilegeEscalation: false => no_new_privs) the kernel
# refuses to exec a file that carries capabilities. Strip them.
RUN apk add --no-cache libcap && setcap -r /usr/bin/caddy && apk del libcap
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
