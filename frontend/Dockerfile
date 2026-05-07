# Dockerfile multietapa para el frontend de Astro

# Etapa 1: etapa de construcción
FROM node:20-alpine as builder

WORKDIR /app

# Copia los ficheros de paquetes
COPY package*.json ./

# Instala dependencias
RUN npm ci

# Copia el código fuente
COPY . .

# Construye el sitio estático
RUN npm run build

# Etapa 2: etapa de desarrollo
FROM node:20-alpine as development

WORKDIR /app

# Copia solo los ficheros de paquetes (el código fuente se montará como volumen)
COPY package*.json ./

# Instala dependencias
RUN npm ci

# Expone el puerto 4321 para el servidor de desarrollo de Astro
EXPOSE 4321

# Arranca el servidor de desarrollo de Astro con --host para escuchar en todas las interfaces
# El código fuente se montará como volumen para recarga en caliente
CMD ["npm", "run", "dev", "--", "--host"]

# Etapa 3: etapa de producción (Nginx)
FROM nginx:1.27-alpine as production

# Copia la configuración de Nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Copia los ficheros estáticos construidos desde la etapa de construcción
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Arranca Nginx
CMD ["nginx", "-g", "daemon off;"]
