FROM cgr.dev/chainguard/python:latest-dev@sha256:8a5780972067cfba4592b10e786a889807ed876c1100f89410fd0ed4e398992c AS builder

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

FROM cgr.dev/chainguard/python:latest@sha256:60e3c0d33ab77e50ace0850ccdf6eaec825ce89dad9b1ec2b0300a2070892b05

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /venv /venv
COPY --from=builder --chown=65532:65532 /app /app
USER 65532

EXPOSE 8000
ENTRYPOINT ["/venv/bin/python"]
CMD ["-m", "gunicorn", "blog_project.wsgi:application", "--bind", "0.0.0.0:8000"]
