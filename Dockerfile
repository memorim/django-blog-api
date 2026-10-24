FROM cgr.dev/chainguard/python:latest-dev@sha256:c179c7d8e23caed59a51ff74d4742f8f8d3f16af4c33c40acaf8d3ee07234592 AS builder

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

FROM cgr.dev/chainguard/python:latest@sha256:fd6d0771e8ec99b1710dfc3d72ca19ba2ff6b14f72b7978922ab0c8acb72c3f3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /venv /venv
COPY --from=builder --chown=65532:65532 /app /app
USER 65532

EXPOSE 8000
ENTRYPOINT ["/venv/bin/python"]
CMD ["-m", "gunicorn", "blog_project.wsgi:application", "--bind", "0.0.0.0:8000"]
