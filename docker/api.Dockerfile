FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY apps ./apps
COPY packs ./packs

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
