# Traefik Integration Guide

## Overview

ChatMock includes production-ready Traefik integration for:
- Automatic HTTPS with Let's Encrypt
- Reverse proxy configuration
- Load balancing support
- Health monitoring
- CORS handling

## Prerequisites

1. **Traefik v2.x** installed and running
2. **Docker** and **Docker Compose**
3. **Domain name** pointing to your server
4. **Traefik network** created

## Quick Start

### 1. Create Traefik Network

```bash
docker network create traefik
```

### 2. Configure Environment

Copy and edit the environment file:

```bash
cp .env.example .env
```

Edit `.env` with your domain:

```bash
CHATMOCK_DOMAIN=chatmock.example.com
TRAEFIK_NETWORK=traefik
TRAEFIK_ACME_EMAIL=admin@example.com
```

### 3. Deploy with Traefik

```bash
docker-compose -f docker-compose.traefik.yml up -d
```

### 4. Initial Authentication

```bash
docker-compose -f docker-compose.traefik.yml --profile login up chatmock-login
```

Follow the OAuth flow to authenticate with your ChatGPT account.

### 5. Access Your Instance

- **WebUI**: https://chatmock.example.com/webui
- **API**: https://chatmock.example.com/v1/chat/completions
- **Health**: https://chatmock.example.com/health

## Traefik Configuration

### Basic Traefik Setup

Ensure your Traefik instance has these configurations:

```yaml
# traefik.yml
api:
  dashboard: true

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https

  websecure:
    address: ":443"
    http:
      tls:
        certResolver: letsencrypt

certificatesResolvers:
  letsencrypt:
    acme:
      email: your-email@example.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: traefik
```

### Complete Traefik Docker Compose

Example Traefik setup:

```yaml
version: "3.9"

services:
  traefik:
    image: traefik:v2.10
    container_name: traefik
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    networks:
      - traefik
    ports:
      - "80:80"
      - "443:443"
    environment:
      - CF_API_EMAIL=${CF_API_EMAIL}  # Optional: for Cloudflare DNS
      - CF_API_KEY=${CF_API_KEY}
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik/traefik.yml:/traefik.yml:ro
      - ./traefik/acme.json:/acme.json
      - ./traefik/config.yml:/config.yml:ro
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.traefik.entrypoints=websecure"
      - "traefik.http.routers.traefik.rule=Host(`traefik.example.com`)"
      - "traefik.http.routers.traefik.service=api@internal"
      - "traefik.http.routers.traefik.tls.certresolver=letsencrypt"

networks:
  traefik:
    external: true
```

## ChatMock Traefik Labels

The `docker-compose.traefik.yml` includes these labels:

```yaml
labels:
  # Enable Traefik
  - "traefik.enable=true"

  # HTTP to HTTPS redirect
  - "traefik.http.routers.chatmock-http.rule=Host(`${CHATMOCK_DOMAIN}`)"
  - "traefik.http.routers.chatmock-http.entrypoints=web"
  - "traefik.http.routers.chatmock-http.middlewares=chatmock-https-redirect"

  # HTTPS Router
  - "traefik.http.routers.chatmock.rule=Host(`${CHATMOCK_DOMAIN}`)"
  - "traefik.http.routers.chatmock.entrypoints=websecure"
  - "traefik.http.routers.chatmock.tls.certresolver=letsencrypt"

  # Service
  - "traefik.http.services.chatmock.loadbalancer.server.port=8000"
```

## Advanced Configuration

### Custom Middleware

Add authentication middleware:

```yaml
labels:
  # Basic Auth
  - "traefik.http.middlewares.chatmock-auth.basicauth.users=user:$$apr1$$..."
  - "traefik.http.routers.chatmock.middlewares=chatmock-auth"
```

### Rate Limiting

```yaml
labels:
  # Rate limit
  - "traefik.http.middlewares.chatmock-ratelimit.ratelimit.average=100"
  - "traefik.http.middlewares.chatmock-ratelimit.ratelimit.burst=50"
  - "traefik.http.routers.chatmock.middlewares=chatmock-ratelimit"
```

### IP Whitelist

```yaml
labels:
  # IP whitelist
  - "traefik.http.middlewares.chatmock-ipwhitelist.ipwhitelist.sourcerange=127.0.0.1/32,192.168.1.0/24"
  - "traefik.http.routers.chatmock.middlewares=chatmock-ipwhitelist"
```

### Path-based Routing

Route different paths to different services:

```yaml
labels:
  # API endpoint
  - "traefik.http.routers.chatmock-api.rule=Host(`${CHATMOCK_DOMAIN}`) && PathPrefix(`/v1`)"
  - "traefik.http.routers.chatmock-api.entrypoints=websecure"
  - "traefik.http.routers.chatmock-api.tls.certresolver=letsencrypt"

  # WebUI endpoint
  - "traefik.http.routers.chatmock-webui.rule=Host(`${CHATMOCK_DOMAIN}`) && PathPrefix(`/webui`)"
  - "traefik.http.routers.chatmock-webui.entrypoints=websecure"
  - "traefik.http.routers.chatmock-webui.tls.certresolver=letsencrypt"
```

## SSL/TLS Configuration

### Let's Encrypt

The default configuration uses Let's Encrypt HTTP challenge:

```yaml
labels:
  - "traefik.http.routers.chatmock.tls.certresolver=letsencrypt"
```

### Cloudflare DNS Challenge

For DNS challenge (works behind firewall):

```yaml
# In Traefik configuration
certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@example.com
      storage: /acme.json
      dnsChallenge:
        provider: cloudflare
        resolvers:
          - "1.1.1.1:53"
          - "8.8.8.8:53"
```

### Custom Certificates

Use your own certificates:

```yaml
labels:
  - "traefik.http.routers.chatmock.tls.domains[0].main=chatmock.example.com"
  - "traefik.http.routers.chatmock.tls.domains[0].sans=*.chatmock.example.com"
```

## Monitoring

### Health Checks

Traefik automatically monitors ChatMock health:

```yaml
labels:
  - "traefik.http.services.chatmock.loadbalancer.healthcheck.path=/health"
  - "traefik.http.services.chatmock.loadbalancer.healthcheck.interval=10s"
```

### Traefik Dashboard

Access Traefik dashboard to monitor:
- Active routers and services
- Health check status
- Certificate status
- Request metrics

## High Availability

### Multiple Instances

Scale ChatMock horizontally:

```bash
docker-compose -f docker-compose.traefik.yml up -d --scale chatmock=3
```

Traefik will automatically load balance between instances.

### Sticky Sessions

For session affinity:

```yaml
labels:
  - "traefik.http.services.chatmock.loadbalancer.sticky.cookie=true"
  - "traefik.http.services.chatmock.loadbalancer.sticky.cookie.name=chatmock_session"
```

## Troubleshooting

### Certificate Issues

Check certificate status:
```bash
docker logs traefik | grep -i acme
```

Verify domain DNS:
```bash
dig chatmock.example.com
nslookup chatmock.example.com
```

### Connection Issues

Check if Traefik can reach ChatMock:
```bash
docker exec traefik wget -O- http://chatmock:8000/health
```

Verify network connection:
```bash
docker network inspect traefik
```

### Label Issues

View applied labels:
```bash
docker inspect chatmock | jq '.[0].Config.Labels'
```

Test Traefik configuration:
```bash
docker exec traefik traefik healthcheck
```

## Security Best Practices

1. **Use Strong TLS**: Enable TLS 1.2+ only
   ```yaml
   tls:
     options:
       default:
         minVersion: VersionTLS12
   ```

2. **Enable Security Headers**:
   ```yaml
   - "traefik.http.middlewares.chatmock-security.headers.stsSeconds=31536000"
   - "traefik.http.middlewares.chatmock-security.headers.stsIncludeSubdomains=true"
   - "traefik.http.middlewares.chatmock-security.headers.stsPreload=true"
   ```

3. **Limit Request Size**:
   ```yaml
   - "traefik.http.middlewares.chatmock-limit.buffering.maxRequestBodyBytes=10485760"
   ```

4. **Use Network Isolation**: Keep ChatMock on internal network, only Traefik on external

## Performance Optimization

### Connection Pooling

```yaml
labels:
  - "traefik.http.services.chatmock.loadbalancer.passhostheader=true"
  - "traefik.http.services.chatmock.loadbalancer.responseforwarding.flushinterval=100ms"
```

### Compression

```yaml
labels:
  - "traefik.http.middlewares.chatmock-compress.compress=true"
  - "traefik.http.routers.chatmock.middlewares=chatmock-compress"
```

## Example Production Setup

Complete production configuration:

```yaml
version: "3.9"

services:
  chatmock:
    image: ghcr.io/thebtf/chatmock:latest
    container_name: chatmock
    command: ["serve"]
    env_file: .env
    environment:
      - CHATGPT_LOCAL_HOME=/data
      - USE_GUNICORN=1
      - GUNICORN_WORKERS=4
    volumes:
      - chatmock_data:/data
    networks:
      - traefik
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik"

      # HTTP to HTTPS redirect
      - "traefik.http.routers.chatmock-http.rule=Host(`chatmock.example.com`)"
      - "traefik.http.routers.chatmock-http.entrypoints=web"
      - "traefik.http.routers.chatmock-http.middlewares=https-redirect"

      # HTTPS
      - "traefik.http.routers.chatmock.rule=Host(`chatmock.example.com`)"
      - "traefik.http.routers.chatmock.entrypoints=websecure"
      - "traefik.http.routers.chatmock.tls.certresolver=letsencrypt"
      - "traefik.http.routers.chatmock.middlewares=security-headers,rate-limit,compress"

      # Service
      - "traefik.http.services.chatmock.loadbalancer.server.port=8000"
      - "traefik.http.services.chatmock.loadbalancer.healthcheck.path=/health"

      # Middlewares
      - "traefik.http.middlewares.security-headers.headers.stsSeconds=31536000"
      - "traefik.http.middlewares.rate-limit.ratelimit.average=100"
      - "traefik.http.middlewares.compress.compress=true"

networks:
  traefik:
    external: true

volumes:
  chatmock_data:
```

## Support

For issues with Traefik integration:
1. Check Traefik logs: `docker logs traefik`
2. Check ChatMock logs: `docker logs chatmock`
3. Verify network connectivity
4. Review Traefik dashboard
5. Consult Traefik documentation: https://doc.traefik.io/traefik/
