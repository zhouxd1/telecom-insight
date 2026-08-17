FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY apps ./apps
COPY packs ./packs

RUN pip install --no-cache-dir -e .

EXPOSE 8001

CMD ["uvicorn", "apps.catalog.main:app", "--host", "0.0.0.0", "--port", "8001"]
