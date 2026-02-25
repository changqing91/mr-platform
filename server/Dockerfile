FROM node:20-bookworm-slim
WORKDIR /app

ENV NODE_ENV=production

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 make g++ && \
    rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./
RUN npm config set registry http://registry.npmmirror.com
RUN npm config set strict-ssl false
RUN npm config set fetch-retries 5
RUN npm config set fetch-retry-mintimeout 20000
RUN npm config set fetch-retry-maxtimeout 120000
RUN npm ci --no-audit --progress=false

COPY . .

RUN npm run build

ENV HOST=0.0.0.0
ENV PORT=1337

EXPOSE 1337
CMD ["npm", "run", "start"]
