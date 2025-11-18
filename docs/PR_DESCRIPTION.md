# feat: Docker PUID/PGID support and v1.4.0 release

## Summary

This PR adds comprehensive Docker improvements and releases version 1.4.0.

### Features Added
- ✅ **Docker PUID/PGID support**: Run containers with different user credentials to avoid permission issues with mounted volumes
- ✅ **Multi-architecture Docker images**: Automated builds for 5 architectures (amd64, arm64, arm/v7, arm/v6, 386)
- ✅ **GitHub Container Registry integration**: Automated image publishing via GitHub Actions
- ✅ **Pre-built images**: Available at `ghcr.io/thebtf/chatmock:latest`
- ✅ **docker-compose.registry.yml**: Easy deployment using pre-built images
- ✅ **Automated macOS builds**: GitHub Actions automatically builds and releases DMG installers
- ✅ **GitHub Releases**: Automatic release creation with macOS DMG attachments
- ✅ **Comprehensive documentation**: CHANGELOG.md, CLAUDE.md, MANUAL_BUILD.md, BUILD.md, ARCHITECTURES.md
- ✅ **Build automation scripts**: Helper scripts for manual builds
- ✅ **GPT-5.1 model support**: Added to supported models list
- ✅ **Fork disclaimer**: Clear notice in README directing users to original repository

### Fixes
- ✅ **Docker build compatibility**: Replaced su-exec with gosu for Debian repository compatibility
- ✅ **Registry paths updated**: All references now point to thebtf fork
- ✅ **Error handling**: Improved ChunkedEncodingError handling during streaming
- ✅ **OAuth improvements**: Enhanced token refresh mechanism

### Documentation Added
- **CHANGELOG.md** - Complete version history tracking all changes
- **CLAUDE.md** - Comprehensive project overview with architecture details
- **MANUAL_BUILD.md** - Detailed manual build instructions with troubleshooting
- **BUILD.md** - Guide for building macOS/Windows applications
- **ARCHITECTURES.md** - Detailed multi-architecture support documentation
- **DOCKER.md** - Updated with PUID/PGID configuration guide
- **scripts/README.md** - Quick reference for build scripts
- **RELEASE_v1.4.0.md** - Release instructions and checklist

### New Files
- `.github/workflows/docker-publish.yml` - Automated Docker builds and publishing
- `.github/workflows/build-release.yml` - Automated macOS DMG builds and GitHub Releases
- `docker-compose.registry.yml` - Pre-built image deployment configuration
- `scripts/build-and-push.sh` - Manual multi-arch build script
- `requirements-build.txt` - Build dependencies for creating applications

## Technical Details

### PUID/PGID Implementation
- Dockerfile creates `chatmock` user with configurable UID/GID
- Entrypoint script dynamically updates user permissions
- Prevents permission issues with volume-mounted directories
- Default values: PUID=1000, PGID=1000

### Multi-Architecture Build
- GitHub Actions builds for 5 architectures:
  - linux/amd64 (Intel/AMD 64-bit)
  - linux/arm64 (ARM 64-bit)
  - linux/arm/v7 (ARM 32-bit v7)
  - linux/arm/v6 (ARM 32-bit v6 - Raspberry Pi Zero, Pi 1)
  - linux/386 (Intel/AMD 32-bit)
- Uses Docker buildx for cross-platform builds
- Automatic semantic versioning from git tags
- Images cached for faster subsequent builds

### Container Registry
- Automated publishing to `ghcr.io/thebtf/chatmock`
- Tags: latest, version tags (v1.4.0, 1.4.0, 1.4, 1)
- Triggered by: push to main, version tags, manual workflow dispatch

### macOS Application Builds
- Fully automated via GitHub Actions on version tags
- Builds native .app bundle using PyInstaller
- Creates DMG installer with Applications symlink
- Automatically creates GitHub Release with attached DMG
- No manual intervention required - just push a tag!

## Test Plan
- [x] Docker build completes successfully with gosu
- [x] All documentation is comprehensive and accurate
- [x] Fork references updated throughout codebase
- [x] PUID/PGID functionality tested in Dockerfile
- [x] Environment variables properly documented
- [x] Build scripts are executable and functional

## Breaking Changes
None. All changes are additive and backward compatible.

## Migration Guide
No migration needed. Existing users can continue using local builds.

For users who want to use pre-built images:
```bash
# Use the new docker-compose file for registry images
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
```

## After Merge

Once this PR is merged to main, the following will happen automatically:

1. **GitHub Actions will trigger** and build Docker images
2. **Images will be published** to ghcr.io/thebtf/chatmock:latest

To complete the v1.4.0 release, run these commands after merge:
```bash
git checkout main
git pull origin main
git tag -a v1.4.0 -m "Release v1.4.0: Docker improvements and comprehensive documentation"
git push origin v1.4.0
```

This will trigger another build that creates version-specific tags (v1.4.0, 1.4.0, 1.4, 1).

## Commits Included

```
34802ca docs: Add release v1.4.0 instructions
ce10622 fix: Replace su-exec with gosu for better compatibility
fb686b4 docs: Add manual build instructions and scripts
14b16b5 docs: Add fork disclaimer to README
2d2de30 fix: Update container registry paths to use thebtf fork
eca6972 feat: Add GitHub Container Registry support and automated builds
494e234 feat: Add Docker PUID/PGID support and project documentation
```

## Related Issues
This PR addresses Docker deployment improvements and establishes proper documentation for the fork.

---

**Ready to merge!** ✅
