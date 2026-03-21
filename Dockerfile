# Usa Python oficial como base
FROM python:3.11-slim

# Instalar dependencias del sistema operativo (Incluyendo Tesseract y Español)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Configurar el directorio de trabajo
WORKDIR /app

# Copiar el archivo de dependencias y las instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código del proyecto
COPY . .

# Exponer el puerto
EXPOSE 10000

# Comando para iniciar la aplicación con gunicorn (Render inyecta su propio $PORT)
CMD gunicorn --workers 2 --bind 0.0.0.0:${PORT:-10000} app:app --timeout 120
