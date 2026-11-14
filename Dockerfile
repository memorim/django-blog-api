FROM cgr.dev/chainguard/python:latest-dev@sha256:6b7c43c25f9446e8b1cf850797826a3d40b7cccdc6370c6e1b31cb28adae0a18 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER root
WORKDIR /app

COPY requirements.txt .
RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt \
    && /venv/bin/pip uninstall -y setuptools wheel \
    && /venv/bin/pip uninstall -y pip

COPY . .
RUN /venv/bin/python manage.py collectstatic --noinput

FROM cgr.dev/chainguard/python:latest@sha256:a57ac9d33d8ca6eb2946d1d7e93a5600153d02e0c7c1fa3a322fc343f89451f5

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /venv /venv
COPY --from=builder --chown=65532:65532 /app /app
USER 65532

EXPOSE 8000
ENTRYPOINT ["/venv/bin/python"]
CMD ["-m", "gunicorn", "blog_project.wsgi:application", "--bind", "0.0.0.0:8000"]
