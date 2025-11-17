# Supported Architectures

ChatMock Docker images are built for multiple architectures to support various hardware platforms.

## Currently Supported Architectures

Our Docker images are available for the following platforms:

### ✅ linux/amd64
- **Description**: 64-bit Intel and AMD processors
- **Use cases**: Desktop computers, servers, cloud instances
- **Common platforms**: x86_64, x64
- **Examples**:
  - Standard PCs and laptops
  - AWS EC2, Google Cloud, Azure VMs
  - Most cloud providers

### ✅ linux/arm64
- **Description**: 64-bit ARM processors
- **Use cases**: Modern ARM servers, embedded systems, newer single-board computers
- **Common platforms**: aarch64, ARMv8
- **Examples**:
  - Apple Silicon Macs (M1, M2, M3)
  - Raspberry Pi 4, 400, CM4 (running 64-bit OS)
  - AWS Graviton instances
  - NVIDIA Jetson series
  - Modern ARM servers

### ✅ linux/arm/v7
- **Description**: 32-bit ARM v7 processors
- **Use cases**: Older ARM devices, 32-bit single-board computers
- **Common platforms**: armhf, armv7l
- **Examples**:
  - Raspberry Pi 2, 3 (running 32-bit OS)
  - BeagleBone boards
  - Older ARM-based IoT devices
  - Many embedded Linux systems

## Using Multi-Architecture Images

Docker automatically selects the correct architecture for your system:

```bash
# This automatically pulls the right architecture
docker pull ghcr.io/thebtf/chatmock:latest

# Verify which architecture you got
docker image inspect ghcr.io/thebtf/chatmock:latest | grep Architecture
```

## Platform-Specific Pull

To explicitly pull a specific architecture:

```bash
# Force amd64
docker pull --platform linux/amd64 ghcr.io/thebtf/chatmock:latest

# Force arm64
docker pull --platform linux/arm64 ghcr.io/thebtf/chatmock:latest

# Force arm/v7
docker pull --platform linux/arm/v7 ghcr.io/thebtf/chatmock:latest
```

## Windows and macOS Support

### Windows
**Linux containers on Windows work through virtualization:**
- ✅ **Windows 10/11 with Docker Desktop + WSL2**: Fully supported
- ✅ **Windows Server with Docker**: Fully supported
- ❌ **Native Windows containers**: Not supported (requires different base image)

**How to run on Windows:**
1. Install Docker Desktop for Windows
2. Enable WSL2 integration
3. Use the Linux images normally - Docker Desktop handles the virtualization

### macOS
**Linux containers on macOS work through virtualization:**
- ✅ **macOS with Docker Desktop**: Fully supported
- ✅ **Apple Silicon (M1/M2/M3)**: Uses linux/arm64 image for better performance
- ✅ **Intel Macs**: Uses linux/amd64 image

## Other Architectures

### Can we add more architectures?

Additional Linux architectures that *could* be supported (but currently aren't):

- **linux/386**: 32-bit Intel/AMD
- **linux/arm/v6**: Older ARM v6 (Raspberry Pi Zero, Pi 1)
- **linux/ppc64le**: PowerPC 64-bit Little Endian
- **linux/s390x**: IBM System/390
- **linux/riscv64**: RISC-V 64-bit

These aren't included by default because:
1. Build time increases significantly with each architecture
2. GitHub Actions has time limits
3. Most users only need amd64, arm64, or arm/v7
4. Some dependencies may not support all architectures

If you need a specific architecture, you can build locally using the scripts provided.

### What about Windows containers?

Native Windows containers are fundamentally different:
- Require Windows Server base image
- Much larger size (GB instead of MB)
- Different Dockerfile
- Require Windows Server host for building
- Python ecosystem is more complex on Windows containers

**Instead, use Docker Desktop on Windows** which runs our Linux containers perfectly through WSL2.

## Performance Considerations

### Native vs Emulated
- **Native**: Running amd64 on x86_64, or arm64 on ARM hardware = **Full performance**
- **Emulated**: Running arm64 on x86_64 through QEMU = **Slower** (but works)

### Recommended Approach
Always use the native architecture for your platform:
- x86_64 servers → linux/amd64
- Apple Silicon Mac → linux/arm64
- Raspberry Pi 4 (64-bit OS) → linux/arm64
- Raspberry Pi 3 (32-bit OS) → linux/arm/v7

## Building for Specific Architectures

### Using the build script:
```bash
# Build for all supported architectures
./scripts/build-and-push.sh v1.4.0

# Build for specific architecture (local only)
docker buildx build --platform linux/arm64 -t chatmock:arm64 --load .
```

### Modify supported architectures:

Edit `.github/workflows/docker-publish.yml`:
```yaml
platforms: linux/amd64,linux/arm64,linux/arm/v7,linux/386
```

Or edit `scripts/build-and-push.sh`:
```bash
PLATFORMS="linux/amd64,linux/arm64,linux/arm/v7"
```

## Verification

After pulling an image, verify the architecture:

```bash
# Check architecture
docker image inspect ghcr.io/thebtf/chatmock:latest --format '{{.Architecture}}'

# Check OS
docker image inspect ghcr.io/thebtf/chatmock:latest --format '{{.Os}}'

# Full manifest inspection
docker manifest inspect ghcr.io/thebtf/chatmock:latest
```

## Troubleshooting

### "exec format error"
This means you're trying to run a binary for a different architecture:
```bash
# Solution: Pull the correct platform
docker pull --platform linux/amd64 ghcr.io/thebtf/chatmock:latest
```

### Slow performance on ARM
If running on ARM but pulling amd64 images:
```bash
# Solution: Explicitly request ARM
docker pull --platform linux/arm64 ghcr.io/thebtf/chatmock:latest
```

### Build fails for specific architecture
Some dependencies may not support all architectures. Check:
1. Python package availability for that platform
2. System package availability in Debian repos
3. Build logs for architecture-specific errors

## Summary

**Currently supported:**
- ✅ linux/amd64 (Intel/AMD 64-bit)
- ✅ linux/arm64 (ARM 64-bit)
- ✅ linux/arm/v7 (ARM 32-bit v7)

**Works on:**
- ✅ Windows (via Docker Desktop + WSL2)
- ✅ macOS (via Docker Desktop)
- ✅ Linux (native)

**Best for:**
- 🖥️ Desktop/Server: amd64
- 🍎 Apple Silicon: arm64
- 🥧 Raspberry Pi: arm64 (64-bit OS) or arm/v7 (32-bit OS)
