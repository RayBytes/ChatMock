# Release v1.4.0 - Instructions

## Current Status

✅ All code changes committed and pushed to branch `claude/update-docs-docker-01Qptso9TSh6tW8vp4Q8LNND`
✅ Docker build issues fixed (replaced su-exec with gosu)
✅ All documentation updated
✅ Tag v1.4.0 created locally

## Next Steps to Publish

You have two options to trigger the automated Docker image build:

### Option 1: Merge to Main via Pull Request (Recommended)

1. Go to: https://github.com/thebtf/ChatMock/compare/main...claude/update-docs-docker-01Qptso9TSh6tW8vp4Q8LNND

2. Click "Create pull request"

3. Title: `feat: Docker PUID/PGID support and v1.4.0 release`

4. Description:
```markdown
## Summary

This PR adds comprehensive Docker improvements and releases version 1.4.0.

### Features Added
- ✅ Docker support with PUID and PGID environment variables for running container with different user credentials
- ✅ Multi-architecture Docker images (linux/amd64, linux/arm64)
- ✅ GitHub Container Registry integration with automated builds
- ✅ Pre-built images at `ghcr.io/thebtf/chatmock:latest`
- ✅ docker-compose.registry.yml for easy deployment
- ✅ Comprehensive documentation (CHANGELOG.md, CLAUDE.md, MANUAL_BUILD.md)
- ✅ Build automation scripts
- ✅ Support for GPT-5.1 models
- ✅ Fork disclaimer in README

### Fixes
- ✅ Replace su-exec with gosu for Debian repository compatibility
- ✅ Fix Docker build errors
- ✅ Update all registry paths to use thebtf fork

### Documentation
- Created CHANGELOG.md tracking all changes
- Created CLAUDE.md with detailed project overview
- Created MANUAL_BUILD.md with manual build instructions
- Updated DOCKER.md with PUID/PGID documentation
- Added build scripts in scripts/ directory

## Test Plan
- [x] Docker build completes successfully
- [x] All documentation is updated
- [x] Fork references updated throughout

After merge, GitHub Actions will automatically:
- Build multi-architecture Docker images
- Publish to ghcr.io/thebtf/chatmock:latest
- Tag as v1.4.0, 1.4, 1
```

5. Click "Create pull request"

6. Review and merge the PR

7. After merge to main, manually create and push the tag:
```bash
git checkout main
git pull origin main
git tag -a v1.4.0 -m "Release v1.4.0"
git push origin v1.4.0
```

This will trigger the GitHub Actions workflow which will:
- Build Docker images for linux/amd64 and linux/arm64
- Push to ghcr.io/thebtf/chatmock with tags: v1.4.0, 1.4.0, 1.4, 1, latest

### Option 2: Manual Workflow Trigger

1. Go to: https://github.com/thebtf/ChatMock/actions/workflows/docker-publish.yml

2. Click "Run workflow" button (on the right side)

3. Select branch: `claude/update-docs-docker-01Qptso9TSh6tW8vp4Q8LNND`

4. Click "Run workflow"

Note: This will build from the current branch, but won't create version tags automatically.

## After Publishing

### Make Package Public (if needed)

By default, GitHub packages are private. To make the Docker images public:

1. Go to: https://github.com/thebtf?tab=packages
2. Click on "chatmock"
3. Click "Package settings"
4. Scroll to "Danger Zone"
5. Click "Change visibility" → "Public"

### Verify Images

After the workflow completes, verify the images:

```bash
# Pull the image
docker pull ghcr.io/thebtf/chatmock:v1.4.0

# Verify multi-architecture support
docker manifest inspect ghcr.io/thebtf/chatmock:v1.4.0

# You should see both linux/amd64 and linux/arm64 in the output
```

### Test the Image

```bash
# Create .env file
cp .env.example .env

# Run login
docker compose -f docker-compose.registry.yml run --rm --service-ports chatmock-login login

# Start server
docker compose -f docker-compose.registry.yml up -d chatmock

# Test
curl -s http://localhost:8000/v1/chat/completions \
   -H 'Content-Type: application/json' \
   -d '{"model":"gpt-5","messages":[{"role":"user","content":"Hello!"}]}'
```

## What's in This Release

### New Features
- Docker PUID/PGID support for permission management
- Multi-architecture images (amd64, arm64)
- GitHub Container Registry integration
- Pre-built images available
- Support for GPT-5.1 models

### Documentation
- CHANGELOG.md - Version history
- CLAUDE.md - Comprehensive project overview
- MANUAL_BUILD.md - Manual build instructions
- Updated DOCKER.md with PUID/PGID docs
- Build automation scripts

### Bug Fixes
- Fixed Docker build by replacing su-exec with gosu
- Updated all references to use fork repository

## All Commits in This Release

```
ce10622 fix: Replace su-exec with gosu for better compatibility
fb686b4 docs: Add manual build instructions and scripts
14b16b5 docs: Add fork disclaimer to README
2d2de30 fix: Update container registry paths to use thebtf fork
eca6972 feat: Add GitHub Container Registry support and automated builds
494e234 feat: Add Docker PUID/PGID support and project documentation
```
