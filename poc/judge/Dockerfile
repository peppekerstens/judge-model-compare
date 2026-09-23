# The judge service. Build from the repo root: docker build -f poc/judge/Dockerfile .
# No torch: the forward pass runs in llama-server on legion-t5.
FROM python:3.13-slim

ARG SEMIF_COMMIT=1f2dea3
RUN pip install --no-cache-dir "transformers==5.17.0" "jinja2>=3.1" huggingface_hub \
    fastapi "uvicorn[standard]" && \
    apt-get update && apt-get install -y --no-install-recommends git && \
    git clone https://github.com/TheoLeeCJ/SemIf /opt/SemIf && \
    git -C /opt/SemIf checkout ${SEMIF_COMMIT} && \
    apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/opt/SemIf/src:/app PYTHONUNBUFFERED=1 HF_HOME=/hf
# Bake the tokenizer of every judge candidate into the image. The service then needs
# no internet, and a model swap is only an environment change plus a restart.
RUN python - <<'EOF'
import transformers
for model, revision in [
    ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    ("Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"),
    ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
]:
    transformers.AutoTokenizer.from_pretrained(model, revision=revision)
    print("baked", model)
EOF

WORKDIR /app
COPY semif-test/remote_semif.py /app/remote_semif.py
COPY poc/judge/app.py /app/app.py
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
