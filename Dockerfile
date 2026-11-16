FROM cgr.dev/chainguard/python:latest-dev@sha256:e0df0ab3cb72380c82f8c5513538152e822a6d8994252663060adea9fdc450c2 AS builder

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

FROM cgr.dev/chainguard/python:latest@sha256:b969ffa5d847b5acd28bd18b12d5b6631cb69c8289f03b309e19b68608724dc6

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /venv /venv
COPY --from=builder --chown=65532:65532 /app /app
USER 65532

EXPOSE 8000
ENTRYPOINT ["/venv/bin/python"]
CMD ["-m", "gunicorn", "blog_project.wsgi:application", "--bind", "0.0.0.0:8000"]
