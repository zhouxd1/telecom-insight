# Multi-stage: Node build + nginx serve for 元景.智数 portal
FROM node:22-alpine AS build
WORKDIR /app
COPY web/package.json ./
RUN npm install
COPY web/ ./
# Production talks to API via nginx /api proxy (same origin)
ENV VITE_API_BASE=
RUN npm run build

FROM nginx:1.27-alpine
COPY docker/web.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
