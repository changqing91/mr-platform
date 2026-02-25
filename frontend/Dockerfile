FROM node:20-alpine AS builder
WORKDIR /app

ARG VITE_TUSD_ENDPOINT=/files
ARG VITE_TUSD_PATH_PREFIX=\\\\192.168.1.80\\upload\\

ENV VITE_TUSD_ENDPOINT=${VITE_TUSD_ENDPOINT}
ENV VITE_TUSD_PATH_PREFIX=${VITE_TUSD_PATH_PREFIX}

COPY package.json package-lock.json* ./
RUN npm config set registry http://registry.npmmirror.com
RUN npm config set strict-ssl false
RUN npm config set fetch-retries 5
RUN npm config set fetch-retry-mintimeout 20000
RUN npm config set fetch-retry-maxtimeout 120000
RUN npm ci --no-audit --progress=false

COPY . .
RUN npm run build

FROM nginx:stable-alpine AS runtime
WORKDIR /usr/share/nginx/html

COPY --from=builder /app/dist ./
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
