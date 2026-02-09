FROM node:20-alpine
WORKDIR /app

ENV NODE_ENV=production
ENV TUSD_HOOK_PORT=3001
ENV TUSD_UPLOAD_DIR=/data/uploads

COPY tusd-hook-rename.js /app/tusd-hook-rename.js
COPY start.sh /app/start.sh

RUN chmod +x /app/start.sh

EXPOSE 3001

CMD ["/app/start.sh"]
