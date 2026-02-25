FROM node:20-alpine AS builder
WORKDIR /app

ARG VITE_TUSD_ENDPOINT=/files
ARG VITE_TUSD_PATH_PREFIX=\\\\192.168.1.80\\upload\\
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV VITE_TUSD_ENDPOINT=${VITE_TUSD_ENDPOINT}
ENV VITE_TUSD_PATH_PREFIX=${VITE_TUSD_PATH_PREFIX}
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

COPY package.json pnpm-lock.yaml* ./
RUN corepack enable
RUN corepack prepare pnpm@9.15.4 --activate
RUN pnpm config set registry http://registry.npmmirror.com
RUN pnpm config set strict-ssl false
RUN if [ -n "$HTTP_PROXY" ]; then pnpm config set proxy "$HTTP_PROXY"; fi
RUN if [ -n "$HTTPS_PROXY" ]; then pnpm config set https-proxy "$HTTPS_PROXY"; fi
RUN if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; else pnpm install --no-frozen-lockfile; fi

COPY . .
RUN pnpm run build

FROM nginx:stable-alpine AS runtime
WORKDIR /usr/share/nginx/html

COPY --from=builder /app/dist ./
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
