FROM python:3.11-slim

# Dependencias nativas que WeasyPrint necesita (cairo, pango, gdk-pixbuf, fuentes, mime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
    fonts-dejavu-core libharfbuzz0b \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiá tu proyecto (app.py, templates/, static/, etc.)
COPY . .

# Gunicorn escucha en $PORT (si no existe, usa 8000)
ENV PYTHONUNBUFFERED=1
CMD sh -c 'gunicorn -w 2 -b 0.0.0.0:${PORT:-8000} app:app'
