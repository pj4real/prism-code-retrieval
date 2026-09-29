FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Model weights and the embedding cache live in volumes so reruns are fast:
#   docker run -v hf-cache:/root/.cache/huggingface -v emb-cache:/app/.cache ...
ENV HF_HOME=/root/.cache/huggingface

# Default: run the official evaluation and write appsretrieval_results.json
# into /app/out (mount a folder there to get the file back).
ENTRYPOINT ["python"]
CMD ["scripts/run_eval.py", "--out", "out/appsretrieval_results.json"]
