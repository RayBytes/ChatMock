FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md chatmock.py prompt.md prompt_gpt5_codex.md /app/
COPY chatmock /app/chatmock
RUN pip install --no-cache-dir .

RUN mkdir -p /data

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000 1455

ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
