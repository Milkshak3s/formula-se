FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

# build-essential only needed if a wheel is missing; libpq5 for psycopg runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The image is safe to run as an arbitrary non-root uid: it writes nothing to
# the image at runtime (artifacts go to B2, temp is an emptyDir). The Kubernetes
# manifests enforce runAsNonRoot + a read-only root filesystem via securityContext;
# Docker Compose runs it as root so its local-storage volume stays writable.
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
