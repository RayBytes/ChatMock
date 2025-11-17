# Build Scripts

This directory contains scripts for building and publishing Docker images.

## Quick Start

### Publish to GitHub Container Registry

```bash
# Build and push with version tag
./scripts/build-and-push.sh v1.0.0

# Build and push as latest
./scripts/build-and-push.sh latest
```

**Prerequisites:**
1. Login to GitHub Container Registry first:
   ```bash
   echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u thebtf --password-stdin
   ```

2. Make sure Docker buildx is available:
   ```bash
   docker buildx version
   ```

## Scripts

### `build-and-push.sh`

Builds multi-architecture Docker images (amd64, arm64) and pushes to GitHub Container Registry.

**Usage:**
```bash
./scripts/build-and-push.sh [version]
```

**Examples:**
```bash
# Build and push v1.0.0 (also creates tags: 1.0.0, 1.0, 1, latest)
./scripts/build-and-push.sh v1.0.0

# Build and push with custom tag
./scripts/build-and-push.sh dev

# Build and push as latest
./scripts/build-and-push.sh latest
```

**What it does:**
- Creates/uses a buildx builder for multi-platform support
- Builds for linux/amd64 and linux/arm64
- For semantic versions (v1.2.3), creates multiple tags
- Pushes all images to ghcr.io/thebtf/chatmock

## Detailed Documentation

For more detailed information about manual building and publishing, see [MANUAL_BUILD.md](../MANUAL_BUILD.md).
