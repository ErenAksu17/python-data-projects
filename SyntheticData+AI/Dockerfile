# Two stages, because the training stack never needs to reach production.
#
# The build stage compiles the dashboard; the runtime stage installs only
# requirements.txt (FastAPI + NumPy + Pydantic, ~40 MB) and copies in the
# already-trained JSON weight bundle. No PyTorch, no scikit-learn: the image
# is small enough to cold-start on a free tier in about a second.

FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY artifacts/model.json artifacts/benchmark.json artifacts/ablation.json ./public/
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VFACTORY_ARTIFACTS=/app/artifacts

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY artifacts/ ./artifacts/
COPY --from=frontend /build/dist ./static

# Never run as root; the app writes nothing outside its own memory.
RUN useradd --create-home --uid 10001 vfactory && chown -R vfactory:vfactory /app
USER vfactory

ENV PYTHONPATH=/app/src \
    VFACTORY_STATIC_DIR=/app/static

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

CMD ["sh", "-c", "uvicorn vfactory.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
