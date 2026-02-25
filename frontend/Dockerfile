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

COPY package.json package-lock.json* ./
RUN npm config set registry http://registry.npmmirror.com
RUN npm config set strict-ssl false
RUN npm config set fetch-retries 5
RUN npm config set fetch-retry-mintimeout 20000
RUN npm config set fetch-retry-maxtimeout 120000
RUN if [ -n "$HTTP_PROXY" ]; then npm config set proxy "$HTTP_PROXY"; fi
RUN if [ -n "$HTTPS_PROXY" ]; then npm config set https-proxy "$HTTPS_PROXY"; fi
RUN if [ -f package-lock.json ]; then sed -i 's#https://registry.npmmirror.com/#http://registry.npmmirror.com/#g' package-lock.json; fi
RUN npm ci --no-audit --progress=false

COPY . .
RUN npm run build

FROM nginx:stable-alpine AS runtime
WORKDIR /usr/share/nginx/html

COPY --from=builder /app/dist ./
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
