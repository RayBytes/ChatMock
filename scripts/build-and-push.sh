#!/usr/bin/env bash
set -euo pipefail

# Build and push multi-architecture Docker images to GitHub Container Registry
# Usage: ./scripts/build-and-push.sh [version]
# Example: ./scripts/build-and-push.sh v1.0.0

VERSION="${1:-latest}"
REGISTRY="ghcr.io"
IMAGE_NAME="thebtf/chatmock"
PLATFORMS="linux/amd64,linux/arm64,linux/arm/v7,linux/arm/v6,linux/386"

echo "Building and pushing Docker image..."
echo "Registry: ${REGISTRY}"
echo "Image: ${IMAGE_NAME}"
echo "Version: ${VERSION}"
echo "Platforms: ${PLATFORMS}"
echo ""

# Check if logged in to GHCR
if ! docker info 2>/dev/null | grep -q "${REGISTRY}"; then
    echo "⚠️  You may not be logged in to ${REGISTRY}"
    echo "Run: echo YOUR_TOKEN | docker login ${REGISTRY} -u YOUR_USERNAME --password-stdin"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create buildx builder if it doesn't exist
if ! docker buildx ls | grep -q "multiarch-builder"; then
    echo "Creating buildx builder..."
    docker buildx create --name multiarch-builder --use
    docker buildx inspect --bootstrap
else
    echo "Using existing buildx builder..."
    docker buildx use multiarch-builder
fi

# Build tags
TAGS=(
    "--tag ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
)

# If version is semantic (v1.2.3), add additional tags
if [[ $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    # v1.2.3 -> 1.2.3, 1.2, 1, latest
    SEMVER="${VERSION#v}"  # Remove 'v' prefix
    MAJOR="${SEMVER%%.*}"
    MINOR="${SEMVER#*.}"
    MINOR="${MINOR%.*}"

    TAGS+=(
        "--tag ${REGISTRY}/${IMAGE_NAME}:${SEMVER}"
        "--tag ${REGISTRY}/${IMAGE_NAME}:${MAJOR}.${MINOR}"
        "--tag ${REGISTRY}/${IMAGE_NAME}:${MAJOR}"
        "--tag ${REGISTRY}/${IMAGE_NAME}:latest"
    )
fi

# Build and push
echo "Building for platforms: ${PLATFORMS}"
echo "Tags: ${TAGS[*]}"
echo ""

docker buildx build \
    --platform "${PLATFORMS}" \
    "${TAGS[@]}" \
    --push \
    .

echo ""
echo "✅ Successfully built and pushed ${IMAGE_NAME}:${VERSION}"
echo ""
echo "To pull the image:"
echo "  docker pull ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
echo ""
echo "To verify multi-architecture:"
echo "  docker manifest inspect ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
