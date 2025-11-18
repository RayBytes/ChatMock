FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PUID=1000 \
    PGID=1000

WORKDIR /app

# Install system dependencies including build tools for packages that need compilation
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gosu \
        gcc \
        g++ \
        make \
        libffi-dev \
        libssl-dev \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN mkdir -p /data && \
    groupadd -g 1000 chatmock && \
    useradd -u 1000 -g chatmock -d /app -s /bin/bash chatmock && \
    chown -R chatmock:chatmock /app /data

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000 1455

ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]

