FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

ENV DOCKER_CONTAINER=true

EXPOSE 8501

CMD ["streamlit", "run", "app_web.py", "--server.port=8501", "--server.address=0.0.0.0"]