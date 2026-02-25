FROM node:20-bookworm-slim
WORKDIR /app

ENV NODE_ENV=production
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 make g++ && \
    rm -rf /var/lib/apt/lists/*

COPY package.json pnpm-lock.yaml* ./
RUN corepack enable
RUN corepack prepare pnpm@9.15.4 --activate
RUN pnpm config set strict-ssl false
RUN if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; else pnpm install --no-frozen-lockfile; fi

COPY . .

RUN npm run build

ENV HOST=0.0.0.0
ENV PORT=1337

EXPOSE 1337
CMD ["pnpm", "run", "start"]
