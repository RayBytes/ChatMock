# ChatMock Documentation

Welcome to the ChatMock documentation! This directory contains comprehensive guides for all aspects of ChatMock.

## 📚 Documentation Index

### Getting Started
- **[Main README](../README.md)** - Project overview and quick start
- **[CLAUDE.md](../CLAUDE.md)** - Detailed project description and architecture

### Deployment & Configuration
- **[DOCKER.md](./DOCKER.md)** - Docker deployment guide with PUID/PGID support
- **[ARCHITECTURES.md](./ARCHITECTURES.md)** - Multi-architecture Docker support (amd64, arm64, arm/v7, arm/v6, 386)
- **[MANUAL_BUILD.md](./MANUAL_BUILD.md)** - Manual Docker build instructions and troubleshooting
- **[BUILD.md](./BUILD.md)** - Building macOS/Windows applications with PyInstaller

### Development & Contributing
- **[CONTRIBUTING.md](./CONTRIBUTING.md)** - Contribution guidelines
- **[CHANGELOG.md](./CHANGELOG.md)** - Version history and release notes

### Release Management
- **[RELEASE_v1.4.0.md](./RELEASE_v1.4.0.md)** - Release instructions for v1.4.0
- **[CREATE_PR_STEPS.md](./CREATE_PR_STEPS.md)** - Step-by-step PR creation guide
- **[PR_DESCRIPTION.md](./PR_DESCRIPTION.md)** - Pull request template

## 🚀 Quick Links

### For Users
- [Docker Deployment](./DOCKER.md) - Get started with Docker
- [Multi-Architecture Support](./ARCHITECTURES.md) - Find your platform
- [Changelog](./CHANGELOG.md) - See what's new

### For Developers
- [Contributing Guide](./CONTRIBUTING.md) - How to contribute
- [Building Applications](./BUILD.md) - Create macOS/Windows apps
- [Manual Build Guide](./MANUAL_BUILD.md) - Build Docker images manually

### For Maintainers
- [Release Process](./RELEASE_v1.4.0.md) - How to create releases
- [PR Guidelines](./CREATE_PR_STEPS.md) - Pull request workflow

## 📦 Release v1.4.0 Features

This fork includes:
- ✅ Docker PUID/PGID support for permission management
- ✅ Multi-architecture Docker images (5 platforms)
- ✅ Automated macOS DMG builds via GitHub Actions
- ✅ GitHub Container Registry integration
- ✅ Comprehensive documentation
- ✅ GPT-5.1 model support

## 🔗 External Resources

- [Original Repository](https://github.com/RayBytes/ChatMock) - RayBytes/ChatMock
- [GitHub Releases](https://github.com/thebtf/ChatMock/releases) - Download pre-built binaries
- [Container Registry](https://github.com/thebtf/ChatMock/pkgs/container/chatmock) - Docker images

## 📝 Documentation Guidelines

When adding new documentation:
1. Place it in the \`docs/\` directory
2. Update this README.md with a link
3. Use clear headings and examples
4. Include troubleshooting sections
5. Keep it up to date with code changes

## 🤝 Contributing to Documentation

Documentation improvements are welcome! Please:
- Follow the existing structure
- Use Markdown best practices
- Include code examples where appropriate
- Test all commands and links
- Submit PRs with clear descriptions

See [CONTRIBUTING.md](./CONTRIBUTING.md) for details.
