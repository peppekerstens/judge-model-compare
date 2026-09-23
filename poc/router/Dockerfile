# The router service. Build from the repo root: docker build -f poc/router/Dockerfile .
FROM python:3.13-slim
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx pyyaml
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY poc/router/app.py /app/app.py
COPY poc/router/router.yaml /app/router.yaml
EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
