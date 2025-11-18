# Manual Docker Build and Publish Guide

This guide explains how to manually build and publish multi-architecture Docker images to GitHub Container Registry.

## Prerequisites

1. Docker with buildx support (Docker Desktop or Docker Engine 19.03+)
2. GitHub Personal Access Token with `write:packages` scope

## Step 1: Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name (e.g., "Docker GHCR Push")
4. Select scope: `write:packages` (this includes `read:packages`)
5. Click "Generate token"
6. **Save the token** - you won't be able to see it again!

## Step 2: Login to GitHub Container Registry

```bash
# Login to GHCR
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Example:
# echo ghp_xxxxxxxxxxxx | docker login ghcr.io -u thebtf --password-stdin
```

## Step 3: Create and Use Buildx Builder

```bash
# Create a new builder instance that supports multi-platform builds
docker buildx create --name multiarch-builder --use

# Bootstrap the builder (downloads necessary components)
docker buildx inspect --bootstrap
```

## Step 4: Build and Push Multi-Architecture Images

### Option A: Build and push in one command

```bash
# Build for both amd64 and arm64, and push to registry
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/thebtf/chatmock:latest \
  --tag ghcr.io/thebtf/chatmock:v1.0.0 \
  --push \
  .
```

### Option B: Build with more tags

```bash
# Build with multiple tags
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/thebtf/chatmock:latest \
  --tag ghcr.io/thebtf/chatmock:1.0.0 \
  --tag ghcr.io/thebtf/chatmock:1.0 \
  --tag ghcr.io/thebtf/chatmock:1 \
  --push \
  .
```

### Option C: Build without pushing (for testing)

```bash
# Build and load to local docker (only works for current architecture)
docker buildx build \
  --platform linux/amd64 \
  --tag chatmock:test \
  --load \
  .

# Test the image locally
docker run --rm chatmock:test --help
```

## Step 5: Verify the Published Image

```bash
# Pull the image to verify it was published
docker pull ghcr.io/thebtf/chatmock:latest

# Check image details
docker manifest inspect ghcr.io/thebtf/chatmock:latest
```

You should see multiple architectures listed in the output.

## Step 6: Make the Package Public (Optional)

By default, packages are private. To make them public:

1. Go to https://github.com/thebtf?tab=packages
2. Click on your package (chatmock)
3. Click "Package settings"
4. Scroll down to "Danger Zone"
5. Click "Change visibility" → "Public"

## Common Issues

### Issue: "permission denied" or "unauthorized"

**Solution**: Make sure you're logged in with a token that has `write:packages` scope:
```bash
docker logout ghcr.io
echo YOUR_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin
```

### Issue: "buildx: command not found"

**Solution**: Update Docker to version 19.03+ or install buildx plugin:
```bash
# Check Docker version
docker version

# On Linux, you may need to enable experimental features
# Add to /etc/docker/daemon.json:
# {
#   "experimental": true
# }
```

### Issue: "multiple platforms feature is currently not supported"

**Solution**: Make sure you're using a buildx builder:
```bash
docker buildx create --name multiarch-builder --use
docker buildx inspect --bootstrap
```

## Quick Reference

```bash
# One-liner to build and push
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/thebtf/chatmock:latest \
  --push \
  .

# Build for specific architecture only
docker buildx build \
  --platform linux/amd64 \
  --tag ghcr.io/thebtf/chatmock:amd64 \
  --push \
  .

# List builders
docker buildx ls

# Remove builder
docker buildx rm multiarch-builder
```

## Notes

- The first multi-platform build may take longer as Docker downloads QEMU emulators
- Building for ARM64 on an x86_64 machine (or vice versa) uses QEMU emulation and will be slower
- You can build for more architectures: `linux/arm/v7`, `linux/arm64`, `linux/amd64`, etc.
- Tags starting with `v` (like `v1.0.0`) will trigger semantic versioning in the GitHub Actions workflow
