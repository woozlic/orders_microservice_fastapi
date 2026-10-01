FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /code
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system -r pyproject.toml
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY src/ ./src/
ENV PYTHONPATH=/code/src
