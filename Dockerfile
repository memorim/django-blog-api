FROM cgr.dev/chainguard/python:latest-dev@sha256:3175d3562cd6fbdf92c574a5f937bbb5a78f04da130d76dead3a5628b1383f80 AS builder

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

FROM cgr.dev/chainguard/python:latest@sha256:d812438658b47b73cb4c089f4cca09bca1ba50f6cd1843133864ee074d9ec49b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /venv /venv
COPY --from=builder --chown=65532:65532 /app /app
USER 65532

EXPOSE 8000
ENTRYPOINT ["/venv/bin/python"]
CMD ["-m", "gunicorn", "blog_project.wsgi:application", "--bind", "0.0.0.0:8000"]
