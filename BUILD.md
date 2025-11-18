# Building ChatMock Applications

This guide explains how to build ChatMock as a standalone application for macOS and Windows.

## Overview

ChatMock can be built as:
- **macOS Application**: Native .app bundle with DMG installer
- **Windows Application**: Standalone .exe (not yet automated via GitHub Actions)

## Automated Builds (GitHub Actions)

### macOS DMG - Fully Automated ✅

When you create a release tag (e.g., `v1.4.0`), GitHub Actions automatically:
1. Builds the macOS application
2. Creates a DMG installer
3. Creates a GitHub Release
4. Attaches the DMG to the release

**No manual action required!** Just push a tag:
```bash
git tag -a v1.4.0 -m "Release v1.4.0"
git push origin v1.4.0
```

Within ~10-15 minutes:
- Docker images will be built for all architectures
- macOS DMG will be built
- GitHub Release will be created with both

### Workflow Files

- `.github/workflows/docker-publish.yml` - Docker multi-arch builds
- `.github/workflows/build-release.yml` - macOS DMG build and GitHub Release creation

## Manual Local Builds

### Prerequisites

Install build dependencies:
```bash
pip install -r requirements-build.txt
```

This installs:
- PyInstaller - Creates standalone executables
- PySide6 - GUI framework
- Pillow - Image processing for icons

### Build macOS Application

```bash
# Build .app bundle only
python build.py --name ChatMock

# Build .app and create DMG installer
python build.py --name ChatMock --dmg
```

Output:
- `dist/ChatMock.app` - macOS application bundle
- `dist/ChatMock.dmg` - DMG installer (if --dmg flag used)

### Build Windows Application

```bash
# On Windows
python build.py --name ChatMock
```

Output:
- `dist/ChatMock.exe` - Windows executable

## Build Script Options

The `build.py` script supports several options:

```bash
python build.py [options]

Options:
  --name NAME       Application name (default: ChatMock)
  --entry FILE      Entry point script (default: gui.py)
  --icon FILE       Icon PNG file (default: icon.png)
  --radius FLOAT    Icon corner radius ratio (default: 0.22)
  --square          Use square icons instead of rounded
  --dmg             Create DMG installer (macOS only)
```

## Build Process Details

### What build.py Does

1. **Icon Generation**
   - Converts PNG icon to platform-specific format
   - macOS: Generates .icns with multiple resolutions
   - Windows: Generates .ico with multiple sizes
   - Applies rounded corners (configurable)

2. **PyInstaller Packaging**
   - Creates standalone executable
   - Bundles all dependencies
   - Includes icon and resources
   - Sets up platform-specific metadata

3. **Platform-Specific Post-Processing**
   - macOS: Patches Info.plist with bundle identifier
   - macOS: Creates DMG with Applications symlink
   - Sets proper permissions and signatures

### macOS DMG Structure

The DMG installer includes:
- `ChatMock.app` - The application
- `Applications` - Symlink for easy installation

Users can drag ChatMock.app to Applications folder.

## Troubleshooting

### macOS: "iconutil: command not found"

Install Xcode Command Line Tools:
```bash
xcode-select --install
```

### macOS: "App is damaged and can't be opened"

This happens because the app isn't signed. Users need to run:
```bash
xattr -dr com.apple.quarantine /Applications/ChatMock.app
```

Or you can add code signing (requires Apple Developer account):
```bash
codesign --deep --force --sign "Developer ID" ChatMock.app
```

### Windows: Missing DLLs

Make sure all dependencies are installed:
```bash
pip install -r requirements-build.txt
```

### Build Fails with Import Errors

Ensure you're in a clean environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-build.txt
python build.py --dmg
```

## File Structure

```
ChatMock/
├── build.py              # Build script
├── gui.py                # GUI application entry point
├── icon.png              # Application icon source
├── requirements.txt      # Runtime dependencies
├── requirements-build.txt # Build dependencies
├── build/                # Build artifacts (temporary)
│   ├── icons/           # Generated icon files
│   └── dmg_staging/     # DMG creation staging
└── dist/                # Build output
    ├── ChatMock.app     # macOS application
    ├── ChatMock.dmg     # macOS installer
    └── ChatMock.exe     # Windows executable
```

## GitHub Release Assets

Each release includes:

1. **ChatMock.dmg** - macOS installer
   - Built automatically by GitHub Actions
   - Ready to download and install
   - No manual building required

2. **Source code** (automatically added by GitHub)
   - `.zip` and `.tar.gz` archives
   - Complete source at that tag

## Future Enhancements

Potential improvements:
- [ ] Windows executable automation via GitHub Actions
- [ ] Code signing for macOS (requires Apple Developer account)
- [ ] Code signing for Windows (requires certificate)
- [ ] Linux AppImage builds
- [ ] Homebrew Cask integration
- [ ] Automated release notes generation

## Development Workflow

For contributors building locally:

```bash
# 1. Make changes to code
vim chatmock/something.py

# 2. Test changes
python chatmock.py serve

# 3. Build application
python build.py --dmg

# 4. Test built application
open dist/ChatMock.dmg
```

## CI/CD Pipeline

The complete release process:

```
Tag Push (v1.4.0)
    │
    ├─> Docker Build Workflow
    │   ├─ Build linux/amd64
    │   ├─ Build linux/arm64
    │   ├─ Build linux/arm/v7
    │   ├─ Build linux/arm/v6
    │   ├─ Build linux/386
    │   └─ Push to ghcr.io
    │
    └─> Build & Release Workflow
        ├─ Build macOS DMG
        ├─ Create GitHub Release
        └─ Attach DMG to release
```

Result: Fully automated release with Docker images and macOS installer!

## Support

For build issues:
- Check this documentation
- Review GitHub Actions logs
- Open an issue with build output
- Include platform and Python version

## References

- [PyInstaller Documentation](https://pyinstaller.org/)
- [PySide6 Documentation](https://doc.qt.io/qtforpython-6/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
