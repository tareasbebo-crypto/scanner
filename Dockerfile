# Usa Python oficial como base
FROM python:3.11-slim

# Instalar dependencias del sistema operativo
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Configurar el directorio de trabajo
WORKDIR /app

# Copiar el archivo de dependencias
COPY requirements.txt .

# Instalar pip actualizado y luego las dependencias
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código del proyecto
COPY . .

# Crear carpetas necesarias
RUN mkdir -p uploads static/img

# Variables de entorno
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Exponer el puerto
EXPOSE 10000

# Comando para iniciar la aplicación con gunicorn
CMD gunicorn --workers 2 --bind 0.0.0.0:${PORT:-10000} app:app --timeout 120
