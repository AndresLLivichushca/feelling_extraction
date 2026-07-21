# Usa la imagen oficial de Playwright con Python y Chromium preinstalado
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

# Variable para forzar headless en los scrapers dentro del contenedor
ENV DOCKER_CONTAINER=true

EXPOSE 8501

CMD ["streamlit", "run", "app_web.py", "--server.port=8501", "--server.address=0.0.0.0"]