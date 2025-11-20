from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
import plistlib
from PIL import Image


ROOT = Path(__file__).parent.resolve()
BUILD_DIR = ROOT / "build"
ICONS_DIR = BUILD_DIR / "icons"


def info(msg: str) -> None:
    print(f"[build] {msg}")


def ensure_dirs() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)


def load_icon_png(path: Path) -> Image.Image:
    if Image is None:
        raise RuntimeError("Pillow is required to process icons.")
    img = Image.open(path).convert("RGBA")
    size = max(img.width, img.height)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - img.width) // 2
    y = (size - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def rounded(img: Image.Image, radius_ratio: float = 0.22) -> Image.Image:
    if Image is None:
        return img
    w, h = img.size
    r = int(min(w, h) * max(0.0, min(radius_ratio, 0.5)))
    if r <= 0:
        return img
    mask = Image.new("L", (w, h), 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, w, h), radius=r, fill=255)
    out = img.copy()
    out.putalpha(mask)
    return out


def make_windows_ico(src_png: Path, out_ico: Path, radius_ratio: float) -> Path:
    info("Generating Windows .ico")
    square = load_icon_png(src_png)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [rounded(square.resize((s, s), Image.LANCZOS), radius_ratio) for s in sizes]
    images[0].save(out_ico, format="ICO", sizes=[(s, s) for s in sizes])
    return out_ico


def make_macos_icns(src_png: Path, out_icns: Path, radius_ratio: float) -> Path:
    info("Generating macOS .icns")
    iconset = BUILD_DIR / "icon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True, exist_ok=True)

    square = load_icon_png(src_png)
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    mapping = {
        16:  ["icon_16x16.png", "icon_32x32.png"],
        32:  ["icon_16x16@2x.png"],
        64:  ["icon_32x32@2x.png"],
        128: ["icon_128x128.png", "icon_256x256.png"],
        256: ["icon_128x128@2x.png"],
        512: ["icon_512x512.png"],
        1024:["icon_512x512@2x.png"],
    }
    for s in sizes:
        img = rounded(square.resize((s, s), Image.LANCZOS), radius_ratio)
        for name in mapping.get(s, []):
            img.save(iconset / name, format="PNG")

    try:
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out_icns)], check=True)
    except Exception as e:
        raise RuntimeError("Failed to create .icns. Ensure Xcode command line tools are installed (iconutil).\n"
                           f"Details: {e}")
    finally:
        shutil.rmtree(iconset, ignore_errors=True)
    return out_icns


def pyinstaller_add_data_arg(src: Path, dest: str) -> str:
    sep = ";" if os.name == "nt" else ":"
    return f"{src}{sep}{dest}"


def run_pyinstaller(entry: Path, name: str, icon: Path | None, extra_data: list[tuple[Path, str]], bundle_id: str | None = None) -> None:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--windowed", "--noconfirm",
        "--name", name,
    ]
    if bundle_id and platform.system().lower() == "darwin":
        cmd += ["--osx-bundle-identifier", bundle_id]
    if icon is not None:
        cmd += ["--icon", str(icon)]
    for (src, dest) in extra_data:
        cmd += ["--add-data", pyinstaller_add_data_arg(src, dest)]
    cmd.append(str(entry))
    info("Running: " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def patch_macos_plist(app_path: Path, bundle_id: str, icon_base_name: str = "appicon") -> None:
    info("Patching macOS Info.plist")
    plist_path = app_path / "Contents" / "Info.plist"
    if not plist_path.exists():
        info(f"No Info.plist at {plist_path}, skipping patch")
        return
    with plist_path.open("rb") as f:
        data = plistlib.load(f)
    data["CFBundleIdentifier"] = bundle_id
    data["CFBundleName"] = data.get("CFBundleName") or app_path.stem
    data["CFBundleDisplayName"] = data.get("CFBundleDisplayName") or app_path.stem
    data["CFBundleIconFile"] = icon_base_name
    data["CFBundleIconName"] = icon_base_name
    with plist_path.open("wb") as f:
        plistlib.dump(data, f)

def make_dmg(app_path: Path, dmg_path: Path, volume_name: str) -> None:
    info("Creating DMG")
    staging = BUILD_DIR / "dmg_staging"
    if staging.exists():
        shutil.rmtree(staging)
    (staging).mkdir(parents=True, exist_ok=True)
    shutil.rmtree(staging / app_path.name, ignore_errors=True)
    shutil.copytree(app_path, staging / app_path.name, symlinks=True)
    try:
        os.symlink("/Applications", staging / "Applications")
    except FileExistsError:
        pass
    dmg_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "hdiutil", "create", "-volname", volume_name,
        "-srcfolder", str(staging),
        "-format", "UDZO",
        "-imagekey", "zlib-level=9",
        str(dmg_path)
    ], check=True)
    shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="ChatMock")
    parser.add_argument("--entry", default="gui.py")
    parser.add_argument("--icon", default="icon.png")
    parser.add_argument("--radius", type=float, default=0.22)
    parser.add_argument("--square", action="store_true")
    parser.add_argument("--dmg", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    entry = ROOT / args.entry
    icon_src = ROOT / args.icon
    if not entry.exists():
        raise SystemExit(f"Entry not found: {entry}")
    if not icon_src.exists():
        raise SystemExit(f"Icon PNG not found: {icon_src}")

    os_name = platform.system().lower()
    extra_data: list[tuple[Path, str]] = [(ROOT / "prompt.md", ".")]

    bundle_icon: Path | None = None
    rr = 0.0 if args.square else float(args.radius)
    if os_name == "windows":
        ico = ICONS_DIR / "appicon.ico"
        make_windows_ico(icon_src, ico, rr)
        bundle_icon = ico
        extra_data.append((ico, "."))
    elif os_name == "darwin":
        icns = ICONS_DIR / "appicon.icns"
        make_macos_icns(icon_src, icns, rr)
        bundle_icon = icns
        extra_data.append((icns, "."))
    else:
        png_copy = ICONS_DIR / "appicon.png"
        if Image is not None:
            square = load_icon_png(icon_src).resize((512, 512), Image.LANCZOS)
            square = rounded(square, rr) if rr > 0 else square
            square.save(png_copy)
        else:
            shutil.copy2(icon_src, png_copy)
        extra_data.append((png_copy, "."))

    run_pyinstaller(entry, args.name, bundle_icon, extra_data)
    if os_name == "darwin":
        app_path = ROOT / "dist" / f"{args.name}.app"
        if app_path.exists():
            bid = "com.chatmock.app"
            patch_macos_plist(app_path, bundle_id=bid, icon_base_name="appicon")
            if args.dmg:
                dmg = ROOT / "dist" / f"{args.name}.dmg"
                make_dmg(app_path, dmg, args.name)



if __name__ == "__main__":
    main()
