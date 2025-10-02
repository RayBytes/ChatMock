#!/bin/bash
set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <github-username> <tag-version>"
    echo "Example: $0 RayBytes v1.0.0"
    exit 1
fi

GITHUB_USER="$1"
TAG_VERSION="$2"
FORMULA_FILE="Formula/chatmock.rb"

VERSION="${TAG_VERSION#v}"

ARCHIVE_URL="https://github.com/${GITHUB_USER}/ChatMock/archive/refs/tags/${TAG_VERSION}.tar.gz"
REPO_URL="https://github.com/${GITHUB_USER}/ChatMock"

echo "Downloading archive to calculate SHA256..."
echo "URL: $ARCHIVE_URL"

SHA256=$(curl -sL "$ARCHIVE_URL" | shasum -a 256 | cut -d' ' -f1)

if [ -z "$SHA256" ]; then
    echo "Error: Could not calculate SHA256. Make sure the tag exists and is accessible."
    exit 1
fi

echo "Calculated SHA256: $SHA256"

echo "Updating $FORMULA_FILE..."

cp "$FORMULA_FILE" "$FORMULA_FILE.backup"

sed -i.tmp "s|homepage \".*\"|homepage \"$REPO_URL\"|g" "$FORMULA_FILE"
sed -i.tmp "s|url \".*\"|url \"$ARCHIVE_URL\"|g" "$FORMULA_FILE"
sed -i.tmp "s|sha256 \".*\"|sha256 \"$SHA256\"|g" "$FORMULA_FILE"
sed -i.tmp "s|head \".*\"|head \"$REPO_URL.git\", branch: \"main\"|g" "$FORMULA_FILE"

rm "$FORMULA_FILE.tmp"

echo "Formula updated successfully!"
echo "Updated values:"
echo "  - Homepage: $REPO_URL"
echo "  - URL: $ARCHIVE_URL"
echo "  - SHA256: $SHA256"
echo ""
echo "Formula is ready for release. Now:"
echo "1. Test the formula: brew install --build-from-source ./Formula/chatmock.rb"
echo "2. Commit and push the changes"
echo "3. Create the release/tag: git tag $TAG_VERSION && git push origin $TAG_VERSION"
