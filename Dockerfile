FROM python:3.11-slim-bookworm

# Dependencias nativas que WeasyPrint necesita
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 libharfbuzz0b shared-mime-info fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt \
 && python - <<'PY'
import weasyprint, pydyf
print("== WeasyPrint version:", weasyprint.__version__)
print("== pydyf version:", pydyf.__version__)
PY

COPY . .

ENV PYTHONUNBUFFERED=1
CMD sh -c 'gunicorn -w 2 -b 0.0.0.0:${PORT:-8000} app:app'
