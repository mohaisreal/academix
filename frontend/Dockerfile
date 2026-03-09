# Multi-stage Dockerfile for Astro frontend

# Stage 1: Builder stage
FROM node:20-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the static site
RUN npm run build

# Stage 2: Development stage
FROM node:20-alpine as development

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Expose port 4321 for Astro dev server
EXPOSE 4321

# Start Astro dev server with --host to listen on all interfaces
CMD ["npm", "run", "dev", "--", "--host"]

# Stage 3: Production stage (Nginx)
FROM nginx:1.27-alpine as production

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built static files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
