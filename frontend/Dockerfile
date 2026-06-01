# Dockerfile multietapa para el frontend de Astro

# Etapa 1: etapa de construcción
FROM node:20-alpine AS builder

WORKDIR /app

ENV PNPM_HOME="/pnpm"
ENV PNPM_STORE_DIR="/pnpm/store"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

# Copia los ficheros de paquetes
COPY package.json pnpm-lock.yaml ./

# Instala dependencias
RUN pnpm install --frozen-lockfile

# Copia el código fuente
COPY . .

# Variables de build para Astro (import.meta.env.PUBLIC_*)
ARG PUBLIC_API_URL
ARG BACKEND_API_URL
ENV PUBLIC_API_URL=${PUBLIC_API_URL}
ENV BACKEND_API_URL=${BACKEND_API_URL}

# Construye el sitio estático
RUN pnpm run build

# Etapa 2: etapa de desarrollo
FROM node:20-alpine AS development

WORKDIR /app

ENV PNPM_HOME="/pnpm"
ENV PNPM_STORE_DIR="/pnpm/store"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

# Copia solo los ficheros de paquetes (el código fuente se montará como volumen)
COPY package.json pnpm-lock.yaml ./

# Instala dependencias
RUN pnpm install --frozen-lockfile

# Expone el puerto 4321 para el servidor de desarrollo de Astro
EXPOSE 4321

# Arranca el servidor de desarrollo de Astro con --host para escuchar en todas las interfaces
# El código fuente se montará como volumen para recarga en caliente
CMD ["pnpm", "run", "dev", "--", "--host"]

# Etapa 3: etapa de producción (Nginx)
FROM nginx:1.27-alpine AS production

# Copia la configuración de Nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Copia los ficheros estáticos construidos desde la etapa de construcción
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Arranca Nginx
CMD ["nginx", "-g", "daemon off;"]
