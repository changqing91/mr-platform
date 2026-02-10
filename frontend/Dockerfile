FROM node:20-alpine AS builder
WORKDIR /app

ARG VITE_TUSD_ENDPOINT=/files
ARG VITE_TUSD_PATH_PREFIX=\\\\192.168.1.224\\upload\\

ENV VITE_TUSD_ENDPOINT=${VITE_TUSD_ENDPOINT}
ENV VITE_TUSD_PATH_PREFIX=${VITE_TUSD_PATH_PREFIX}

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:stable-alpine AS runtime
WORKDIR /usr/share/nginx/html

COPY --from=builder /app/dist ./
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
