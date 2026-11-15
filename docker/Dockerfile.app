# CPU image: API + dashboard + tests on synthetic fixtures. No data, no checkpoints inside.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[dev]"
COPY configs ./configs
COPY web ./web
COPY scripts ./scripts
COPY tests ./tests
# data/, results/ and the review database are mounted at runtime (see docker-compose.yml)
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "btqc.serve.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
