FROM python:3.12-slim AS dependencies

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build

COPY requirements.prod.txt .

RUN pip install --no-cache-dir -r requirements.prod.txt


FROM python:3.12-slim AS runtime

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd \
    --no-create-home \
    --shell /usr/sbin/nologin \
    --uid 10001 \
    appuser

WORKDIR /app

COPY --from=dependencies /opt/venv /opt/venv

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
