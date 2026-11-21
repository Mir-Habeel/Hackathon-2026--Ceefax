FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir "certifi>=2025.0.0"

COPY app.py ./
COPY templates ./templates
COPY static ./static

ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
