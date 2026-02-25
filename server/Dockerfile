FROM node:20-bookworm-slim
WORKDIR /app

ENV NODE_ENV=production
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 make g++ && \
    rm -rf /var/lib/apt/lists/*

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

ENV HOST=0.0.0.0
ENV PORT=1337

EXPOSE 1337
CMD ["pnpm", "run", "start"]
