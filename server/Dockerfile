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

COPY package.json package-lock.json* ./
RUN npm config set registry http://registry.npmmirror.com
RUN npm config set strict-ssl false
RUN npm config set fetch-retries 5
RUN npm config set fetch-retry-mintimeout 20000
RUN npm config set fetch-retry-maxtimeout 120000
RUN if [ -n "$HTTP_PROXY" ]; then npm config set proxy "$HTTP_PROXY"; fi
RUN if [ -n "$HTTPS_PROXY" ]; then npm config set https-proxy "$HTTPS_PROXY"; fi
RUN npm ci --no-audit --progress=false

COPY . .

RUN npm run build

ENV HOST=0.0.0.0
ENV PORT=1337

EXPOSE 1337
CMD ["npm", "run", "start"]
