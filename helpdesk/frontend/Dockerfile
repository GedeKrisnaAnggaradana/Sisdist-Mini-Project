# Tahap 1: Build React App
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Tahap 2: Serve dengan Nginx
FROM nginx:alpine

# Copy konfigurasi Nginx kustom untuk SPA
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy hasil build dari Tahap 1
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
