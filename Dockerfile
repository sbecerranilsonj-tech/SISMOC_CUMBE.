# ==============================================================================
# Dockerfile — SISMOC-CUMBE Backend
# Empresa de Transportes El Cumbe S.A.C. (RUC: 20480397731)
# ==============================================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Instalar dependencias del sistema necesarias para PostgreSQL y red
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el codigo del proyecto
COPY . /app/

# Crear directorios para static y media
RUN mkdir -p /app/static /app/media /app/staticfiles

EXPOSE 8000

CMD ["python", "deploy/start.py"]
