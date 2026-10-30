#!/usr/bin/env python3
"""
Darling App Manager - Backend Module
Handles macOS application inspection, Mach-O architecture parsing,
ICNS/PNG extraction, DMG/PKG unpacking, prefix installation,
and FreeDesktop desktop integration.
"""

from __future__ import annotations

import dataclasses
import glob
import gzip
import logging
import os
import pathlib
import plistlib
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zlib
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

try:
    import anything_mac_runtime
except ImportError:
    try:
        from . import anything_mac_runtime
    except Exception:
        anything_mac_runtime = None

# Set up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("anything_mac_backend")

# Architecture Constants (from mach-o/loader.h and mach-o/fat.h)
MH_MAGIC = 0xFEEDFACE
MH_CIGAM = 0xCEFAEDFE
MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE

FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA
FAT_MAGIC_64 = 0xCAFEBABC  # Or 0xcafebabf in some headers
FAT_CIGAM_64 = 0xBFBABECA
FAT_MAGIC_64_ALT = 0xCAFEBABF
FAT_CIGAM_64_ALT = 0xBFBAFECA

CPU_TYPES: Dict[int, str] = {
    7: "i386",
    0x01000007: "x86_64",
    12: "arm",
    0x0100000C: "arm64",
    18: "ppc",
    0x01000012: "ppc64",
}

MACOS_VERSION_NAMES: Dict[str, str] = {
    "10.0": "Cheetah",
    "10.1": "Puma",
    "10.2": "Jaguar",
    "10.3": "Panther",
    "10.4": "Tiger",
    "10.5": "Leopard",
    "10.6": "Snow Leopard",
    "10.7": "Lion",
    "10.8": "Mountain Lion",
    "10.9": "Mavericks",
    "10.10": "Yosemite",
    "10.11": "El Capitan",
    "10.12": "Sierra",
    "10.13": "High Sierra",
    "10.14": "Mojave",
    "10.15": "Catalina",
    "11": "Big Sur",
    "11.0": "Big Sur",
    "12": "Monterey",
    "12.0": "Monterey",
    "13": "Ventura",
    "13.0": "Ventura",
    "14": "Sonoma",
    "14.0": "Sonoma",
    "15": "Sequoia",
    "15.0": "Sequoia",
}


@dataclasses.dataclass
class AppInfo:
    """Metadata describing a macOS Application bundle."""
    bundle_path: str
    bundle_name: str
    display_name: str
    bundle_id: str
    version: str
    build_version: str
    executable_name: str
    executable_path: str
    architectures: List[str]
    arch_summary: str
    is_darling_compatible: bool
    min_os_version: str
    min_os_display: str
    size_bytes: int
    size_formatted: str
    icon_preview_path: Optional[str] = None
    icon_resolutions: Dict[int, str] = dataclasses.field(default_factory=dict)
    source_file: Optional[str] = None
    source_type: str = "app"  # "app", "dmg", "pkg"
    is_installed: bool = False
    installed_path: Optional[str] = None
    desktop_file_path: Optional[str] = None
    temp_dir: Optional[str] = None


def format_size(num_bytes: int) -> str:
    """Formats bytes into human readable string (KB, MB, GB)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024.0 or unit == "TB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} B"


def get_darling_prefix() -> pathlib.Path:
    """Returns the AnythingMac prefix directory path."""
    prefix_env = os.environ.get("ANYTHING_MAC_PREFIX") or os.environ.get("DARLING_PREFIX")
    if prefix_env:
        return pathlib.Path(prefix_env).expanduser()
    p_amac = pathlib.Path("~/.anything-mac").expanduser()
    if p_amac.is_dir():
        return p_amac
    return pathlib.Path("~/.darling").expanduser()


def get_darling_applications_dir() -> pathlib.Path:
    """Returns the Applications directory inside Darling prefix."""
    prefix = get_darling_prefix()
    # In Darling, Applications resides in ~/.darling/Applications
    # or ~/.darling/Volumes/SystemRoot/Applications
    apps_dir = prefix / "Applications"
    return apps_dir


def get_cache_dir() -> pathlib.Path:
    """Returns the cache directory for Darling App Manager."""
    cache = pathlib.Path("~/.cache/anything-mac-manager").expanduser()
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def parse_macho_architectures(file_path: Union[str, pathlib.Path]) -> List[str]:
    """
    Parses a Mach-O binary header to detect CPU architectures
    (x86_64, arm64, Universal 2 fat binary, i386, etc.).
    """
    path = pathlib.Path(file_path)
    if not path.is_file():
        return []

    try:
        with open(path, "rb") as f:
            header = f.read(4096)
    except Exception as e:
        logger.warning("Failed to read Mach-O file %s: %s", path, e)
        return []

    if len(header) < 4:
        return []

    # Check for script (e.g. #!/bin/sh)
    if header.startswith(b"#!"):
        return ["script"]

    magic = struct.unpack(">I", header[:4])[0]
    archs: List[str] = []

    # 1. 32-bit Fat / Universal Binary
    if magic in (FAT_MAGIC, FAT_CIGAM):
        endian = ">" if magic == FAT_MAGIC else "<"
        if len(header) >= 8:
            narchs = struct.unpack(endian + "I", header[4:8])[0]
            offset = 8
            for _ in range(min(narchs, 32)):
                if offset + 20 > len(header):
                    break
                cputype, cpusubtype, arch_offset, size, align = struct.unpack(
                    endian + "IIIII", header[offset : offset + 20]
                )
                arch_name = CPU_TYPES.get(cputype, f"cpu_0x{cputype:x}")
                if arch_name not in archs:
                    archs.append(arch_name)
                offset += 20
        return archs

    # 2. 64-bit Fat / Universal Binary
    if magic in (FAT_MAGIC_64, FAT_CIGAM_64, FAT_MAGIC_64_ALT, FAT_CIGAM_64_ALT):
        endian = ">" if magic in (FAT_MAGIC_64, FAT_MAGIC_64_ALT) else "<"
        if len(header) >= 8:
            narchs = struct.unpack(endian + "I", header[4:8])[0]
            offset = 8
            for _ in range(min(narchs, 32)):
                if offset + 32 > len(header):
                    break
                cputype, cpusubtype, arch_offset, size, align, reserved = struct.unpack(
                    endian + "IIQQII", header[offset : offset + 32]
                )
                arch_name = CPU_TYPES.get(cputype, f"cpu_0x{cputype:x}")
                if arch_name not in archs:
                    archs.append(arch_name)
                offset += 32
        return archs

    # 3. Thin Mach-O (32-bit or 64-bit)
    if magic in (MH_MAGIC, MH_MAGIC_64, MH_CIGAM, MH_CIGAM_64):
        endian = "<" if magic in (MH_CIGAM, MH_CIGAM_64) else ">"
        if len(header) >= 12:
            cputype, cpusubtype = struct.unpack(endian + "II", header[4:12])
            arch_name = CPU_TYPES.get(cputype, f"cpu_0x{cputype:x}")
            archs.append(arch_name)
        return archs

    return []


def format_arch_summary(archs: List[str]) -> Tuple[str, bool, str]:
    """
    Returns (summary_label, is_darling_compatible, badge_class).
    badge_class is 'badge-compat', 'badge-warn', or 'badge-info'.
    """
    if not archs:
        return ("Unknown Binary", True, "badge-warn")

    has_x86_64 = "x86_64" in archs
    has_arm64 = "arm64" in archs
    has_i386 = "i386" in archs

    if has_x86_64 and has_arm64:
        return ("Universal 2 (x86_64 + arm64)", True, "badge-compat")
    elif has_x86_64:
        return ("64-bit Intel (x86_64)", True, "badge-compat")
    elif has_arm64 and not has_x86_64:
        return ("Apple Silicon (arm64 only)", False, "badge-warn")
    elif has_i386:
        return ("32-bit Intel (i386)", True, "badge-info")
    elif "script" in archs:
        return ("Script Executable", True, "badge-info")
    else:
        return (", ".join(archs), False, "badge-warn")


def format_min_os(min_os: str) -> str:
    """Formats minimum macOS version with marketing name if known."""
    if not min_os:
        return "macOS (Any)"
    
    # Clean version
    clean_ver = min_os.strip()
    parts = clean_ver.split(".")
    short_ver = ".".join(parts[:2]) if len(parts) >= 2 else clean_ver
    
    name = MACOS_VERSION_NAMES.get(clean_ver) or MACOS_VERSION_NAMES.get(short_ver) or MACOS_VERSION_NAMES.get(parts[0])
    if name:
        return f"macOS {clean_ver} ({name})"
    return f"macOS {clean_ver}"


def is_macos_version_supported(min_os: str) -> Tuple[bool, str]:
    """
    Treat the deployment target as advisory; it does not prove which APIs an app uses.
    Returns (may_attempt_launch, advisory).
    """
    if not min_os:
        return True, ""
    try:
        parts = [int(p) for p in min_os.split(".") if p.isdigit()]
        if not parts:
            return True, ""
        major = parts[0]
        if major >= 12:
            return True, (
                f"Targets macOS {min_os}; minimum OS metadata cannot predict API compatibility. "
                "Darling will attempt the launch."
            )
        return True, ""
    except Exception:
        return True, ""


def generate_fallback_icon(name: str, size: int = 512) -> Image.Image:
    """
    Generates a modern macOS squircle style fallback icon with Pillow
    when an application lacks an ICNS file or conversion fails.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    padding = int(size * 0.08)
    radius = int(size * 0.22)
    rect = [padding, padding, size - padding, size - padding]

    # Select color palette based on name hash for consistency
    palettes = [
        ((35, 120, 240, 255), (15, 80, 200, 255)),   # macOS Blue
        ((120, 75, 230, 255), (80, 40, 190, 255)),   # Purple
        ((235, 85, 70, 255), (190, 45, 30, 255)),    # Red
        ((40, 180, 120, 255), (20, 140, 80, 255)),   # Green
        ((240, 150, 30, 255), (200, 110, 15, 255)),  # Orange
        ((45, 170, 215, 255), (25, 130, 175, 255)),  # Cyan
    ]
    color_idx = abs(hash(name)) % len(palettes)
    fill_color, border_color = palettes[color_idx]

    # Draw rounded squircle
    draw.rounded_rectangle(
        rect,
        radius=radius,
        fill=fill_color,
        outline=(255, 255, 255, 80),
        width=max(2, int(size * 0.02)),
    )

    # Draw initial letter(s)
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", name)
    initials = (clean_name[:2] if len(clean_name) >= 2 else (clean_name or "A")).upper()

    font = None
    for font_path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, int(size * 0.38))
                break
            except Exception:
                continue

    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initials, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(
        ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
        initials,
        fill=(255, 255, 255, 250),
        font=font,
    )
    return img


def extract_app_icons(
    app_bundle_path: Union[str, pathlib.Path],
    icon_filename: Optional[str] = None,
    dest_dir: Optional[Union[str, pathlib.Path]] = None,
    resolutions: Optional[List[int]] = None,
) -> Dict[int, str]:
    """
    Extracts icons from an .app bundle at resolutions [512, 256, 128, 64, 32].
    Saves PNGs and returns a map of {size: path_to_png}.
    """
    if resolutions is None:
        resolutions = [512, 256, 128, 64, 32]

    bundle = pathlib.Path(app_bundle_path)
    if dest_dir is None:
        cache_apps = get_cache_dir() / "icons"
        cache_apps.mkdir(parents=True, exist_ok=True)
        dest_dir = cache_apps / bundle.stem
    dest_path = pathlib.Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)

    icon_map: Dict[int, str] = {}
    resources_dir = bundle / "Contents" / "Resources"

    # 1. Locate ICNS file
    icns_file: Optional[pathlib.Path] = None

    if icon_filename:
        candidate = resources_dir / icon_filename
        if candidate.is_file():
            icns_file = candidate
        elif not icon_filename.lower().endswith(".icns"):
            candidate = resources_dir / f"{icon_filename}.icns"
            if candidate.is_file():
                icns_file = candidate

    if not icns_file and resources_dir.is_dir():
        for f in resources_dir.glob("*.icns"):
            icns_file = f
            break

    # 2. Extract or generate PNG images
    source_img: Optional[Image.Image] = None

    if icns_file and icns_file.is_file():
        try:
            source_img = Image.open(icns_file)
            source_img.load()
        except Exception as e:
            logger.warning("Pillow could not open ICNS %s: %s", icns_file, e)
            source_img = None

    if source_img is None:
        source_img = generate_fallback_icon(bundle.stem, 512)

    # 3. Save icons at all requested resolutions
    for res in resolutions:
        out_file = dest_path / f"icon_{res}x{res}.png"
        try:
            if source_img.size == (res, res):
                resized = source_img.copy()
            else:
                resized = source_img.resize((res, res), Image.Resampling.LANCZOS)
            resized.save(out_file, format="PNG")
            icon_map[res] = str(out_file)
        except Exception as e:
            logger.warning("Failed saving icon resolution %d: %s", res, e)

    return icon_map


def inspect_app_bundle(
    bundle_path: Union[str, pathlib.Path],
    source_file: Optional[Union[str, pathlib.Path]] = None,
    source_type: str = "app",
    temp_dir: Optional[str] = None,
) -> AppInfo:
    """
    Inspects a `.app` bundle:
    - Parses Info.plist (XML / Binary)
    - Parses Mach-O binary architectures
    - Extracts multi-resolution app icons
    - Calculates bundle size
    - Determines Darling prefix installation status
    """
    path = pathlib.Path(bundle_path).resolve()
    plist_path = path / "Contents" / "Info.plist"

    plist_data: Dict[str, Any] = {}
    if plist_path.is_file():
        try:
            with open(plist_path, "rb") as f:
                plist_data = plistlib.load(f)
        except Exception as e:
            logger.warning("Failed to parse Info.plist %s with plistlib: %s", plist_path, e)
            # Try fallback regex for basic keys if plist is unusual
            try:
                raw_text = plist_path.read_text(errors="ignore")
                for key in ["CFBundleName", "CFBundleDisplayName", "CFBundleIdentifier", "CFBundleExecutable"]:
                    m = re.search(rf"<key>{key}</key>\s*<string>([^<]+)</string>", raw_text)
                    if m:
                        plist_data[key] = m.group(1)
            except Exception:
                pass

    bundle_name = plist_data.get("CFBundleName") or path.stem
    display_name = (
        plist_data.get("CFBundleDisplayName")
        or plist_data.get("CFBundleName")
        or path.stem
    )
    bundle_id = plist_data.get("CFBundleIdentifier") or f"org.darling.{path.stem.lower()}"
    version = plist_data.get("CFBundleShortVersionString") or plist_data.get("CFBundleVersion") or "1.0"
    build_version = str(plist_data.get("CFBundleVersion") or "")
    executable_name = plist_data.get("CFBundleExecutable") or bundle_name
    min_os = str(plist_data.get("LSMinimumSystemVersion") or plist_data.get("MinimumOSVersion") or "")

    # Mach-O inspection
    executable_path = path / "Contents" / "MacOS" / executable_name
    if not executable_path.is_file() and (path / "Contents" / "MacOS").is_dir():
        # Fallback: pick first executable file in Contents/MacOS
        for bin_candidate in (path / "Contents" / "MacOS").iterdir():
            if bin_candidate.is_file():
                executable_path = bin_candidate
                executable_name = bin_candidate.name
                break

    archs = parse_macho_architectures(executable_path)
    arch_summary, is_arch_compat, _ = format_arch_summary(archs)
    is_os_compat, os_reason = is_macos_version_supported(min_os)
    is_compatible = is_arch_compat and is_os_compat
    min_os_display = format_min_os(min_os)

    # Icon extraction
    icon_file = plist_data.get("CFBundleIconFile")
    icon_map = extract_app_icons(path, icon_filename=icon_file)
    preview_icon = icon_map.get(128) or icon_map.get(256) or icon_map.get(512)

    # Calculate bundle size
    total_size = 0
    try:
        for root, dirs, files in os.walk(path):
            for file in files:
                fp = os.path.join(root, file)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except Exception:
        total_size = 0

    # Installation status check
    darling_apps_dir = get_darling_applications_dir()
    installed_app_path = darling_apps_dir / path.name
    is_installed = installed_app_path.is_dir()
    desktop_file = (
        pathlib.Path("~/.local/share/applications").expanduser()
        / f"darling-{bundle_id}.desktop"
    )

    return AppInfo(
        bundle_path=str(path),
        bundle_name=bundle_name,
        display_name=display_name,
        bundle_id=bundle_id,
        version=version,
        build_version=build_version,
        executable_name=executable_name,
        executable_path=str(executable_path),
        architectures=archs,
        arch_summary=arch_summary,
        is_darling_compatible=is_compatible,
        min_os_version=min_os,
        min_os_display=min_os_display,
        size_bytes=total_size,
        size_formatted=format_size(total_size),
        icon_preview_path=preview_icon,
        icon_resolutions=icon_map,
        source_file=str(source_file) if source_file else str(path),
        source_type=source_type,
        is_installed=is_installed,
        installed_path=str(installed_app_path) if is_installed else None,
        desktop_file_path=str(desktop_file) if desktop_file.is_file() else None,
        temp_dir=temp_dir,
    )


# ==============================================================================
# DMG Extraction & Handling
# ==============================================================================

def extract_dmg_with_darling(dmg_path: pathlib.Path, target_dir: pathlib.Path) -> List[pathlib.Path]:
    """
    Attempts to mount DMG using Darling's native hdiutil:
    `darling shell hdiutil attach ...`
    """
    darling_bin = shutil.which("darling")
    if not darling_bin:
        return []

    try:
        # Attach dmg inside Darling
        proc = subprocess.run(
            [darling_bin, "shell", "hdiutil", "attach", "-nobrowse", "-readonly", str(dmg_path)],
            capture_output=True,
            text=True,
            timeout=25,
        )
        if proc.returncode != 0:
            logger.debug("darling hdiutil attach returned %d: %s", proc.returncode, proc.stderr)
            return []

        # Find mountpoint from output (e.g. /Volumes/VolumeName)
        mountpoint = None
        for line in proc.stdout.splitlines():
            if "/Volumes/" in line:
                mountpoint = line.split()[-1]
                break

        if not mountpoint:
            return []

        # Host path to Darling mountpoint
        darling_prefix = get_darling_prefix()
        host_mount = darling_prefix / mountpoint.lstrip("/")
        if not host_mount.is_dir():
            # In some Darling setups, /Volumes is mapped directly or in Volumes/
            host_mount = darling_prefix / "Volumes" / pathlib.Path(mountpoint).name

        found_apps: List[pathlib.Path] = []
        if host_mount.is_dir():
            for app_dir in host_mount.glob("*.app"):
                dest_app = target_dir / app_dir.name
                shutil.copytree(app_dir, dest_app, symlinks=True, dirs_exist_ok=True)
                found_apps.append(dest_app)

        # Detach
        subprocess.run(
            [darling_bin, "shell", "hdiutil", "detach", mountpoint],
            capture_output=True,
            timeout=10,
        )
        return found_apps
    except Exception as e:
        logger.warning("darling hdiutil extraction failed: %s", e)
        return []


def extract_dmg_with_7z(dmg_path: pathlib.Path, target_dir: pathlib.Path) -> List[pathlib.Path]:
    """Attempts to extract DMG using 7z / 7zz / 7za."""
    seven_z = shutil.which("7z") or shutil.which("7zz") or shutil.which("7za")
    if not seven_z:
        return []

    try:
        cmd = [seven_z, "x", str(dmg_path), f"-o{target_dir}", "-y"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if proc.returncode != 0:
            logger.debug("7z returned %d for DMG: %s", proc.returncode, proc.stderr)

        # Search for .app bundle in target_dir
        found_apps: List[pathlib.Path] = []
        for root, dirs, files in os.walk(target_dir):
            for d in dirs:
                if d.endswith(".app"):
                    found_apps.append(pathlib.Path(root) / d)
        return found_apps
    except Exception as e:
        logger.warning("7z DMG extraction failed: %s", e)
        return []


def extract_dmg_with_dmg2img(dmg_path: pathlib.Path, target_dir: pathlib.Path) -> List[pathlib.Path]:
    """Attempts conversion using dmg2img tool if installed."""
    dmg2img_bin = shutil.which("dmg2img")
    if not dmg2img_bin:
        return []

    try:
        img_file = target_dir / "converted.img"
        cmd = [dmg2img_bin, "-i", str(dmg_path), "-o", str(img_file)]
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
        if proc.returncode == 0 and img_file.is_file():
            # Try 7z on the converted img
            return extract_dmg_with_7z(img_file, target_dir)
        return []
    except Exception as e:
        logger.warning("dmg2img conversion failed: %s", e)
        return []


def decompress_udif_dmg_python(dmg_path: pathlib.Path, target_dir: pathlib.Path) -> List[pathlib.Path]:
    """
    Pure Python Apple UDIF (DMG) unpacker:
    Reads the 512-byte 'koly' trailer at the end of the DMG file, parses the
    embedded XML plist describing blkx chunks, and decompresses zlib/raw chunks.
    """
    try:
        file_size = dmg_path.stat().st_size
        if file_size < 512:
            return []

        with open(dmg_path, "rb") as f:
            f.seek(file_size - 512)
            koly = f.read(512)
            if koly[:4] != b"koly":
                logger.debug("DMG does not have koly trailer")
                return []

            # Unpack xml_offset (uint64) and xml_length (uint64) at offset 216
            xml_offset, xml_length = struct.unpack_from(">QQ", koly, 216)
            if xml_offset + xml_length > file_size:
                return []

            f.seek(xml_offset)
            xml_data = f.read(xml_length)
            plist = plistlib.loads(xml_data)

            resource_fork = plist.get("resource-fork", {})
            blkx_list = resource_fork.get("blkx", [])
            if not blkx_list:
                return []

            raw_img_path = target_dir / "extracted_fs.raw"
            with open(raw_img_path, "wb") as out_raw:
                for block in blkx_list:
                    data = block.get("Data")
                    if not data or len(data) < 204:
                        continue

                    # Each 'blkx' data starts with 'mish' header (204 bytes)
                    magic, version, sector_num, sector_cnt, data_off, buffers, block_desc_cnt = struct.unpack_from(
                        ">4sIQQQII", data, 0
                    )
                    if magic != b"mish":
                        continue

                    chunk_offset = 204
                    for _ in range(block_desc_cnt):
                        if chunk_offset + 40 > len(data):
                            break
                        chunk_type, comment, sec_start, sec_count, comp_off, comp_len = struct.unpack_from(
                            ">IIQQQQ", data, chunk_offset
                        )
                        chunk_offset += 40

                        if chunk_type == 0x00000000:
                            # Zero fill
                            out_raw.write(b"\x00" * (sec_count * 512))
                        elif chunk_type == 0x00000001:
                            # Raw uncompressed
                            f.seek(comp_off)
                            raw_chunk = f.read(comp_len)
                            out_raw.write(raw_chunk)
                        elif chunk_type == 0x80000005:
                            # zlib compressed
                            f.seek(comp_off)
                            comp_chunk = f.read(comp_len)
                            try:
                                decomp = zlib.decompress(comp_chunk)
                                out_raw.write(decomp)
                            except Exception:
                                pass
                        elif chunk_type == 0xFFFFFFFE:
                            # Terminator
                            break

            if raw_img_path.is_file() and raw_img_path.stat().st_size > 0:
                # If 7z is present, unpack the raw filesystem image
                seven_res = extract_dmg_with_7z(raw_img_path, target_dir)
                if seven_res:
                    return seven_res

        return []
    except Exception as e:
        logger.debug("Pure Python UDIF unpacker encountered: %s", e)
        return []


def inspect_and_extract_dmg(dmg_path: Union[str, pathlib.Path]) -> List[AppInfo]:
    """
    Inspects a `.dmg` file:
    Extracts the application bundle using available strategies:
    1. Darling native hdiutil
    2. 7-Zip
    3. dmg2img
    4. Pure Python UDIF decompressor
    """
    dmg = pathlib.Path(dmg_path).resolve()
    temp_dir = tempfile.mkdtemp(prefix="darling_dmg_")
    target_dir = pathlib.Path(temp_dir)

    found_apps = (
        extract_dmg_with_darling(dmg, target_dir)
        or extract_dmg_with_7z(dmg, target_dir)
        or extract_dmg_with_dmg2img(dmg, target_dir)
        or decompress_udif_dmg_python(dmg, target_dir)
    )

    # Search recursively if apps were extracted in a subdirectory
    if not found_apps:
        for root, dirs, files in os.walk(target_dir):
            for d in dirs:
                if d.endswith(".app"):
                    found_apps.append(pathlib.Path(root) / d)

    results: List[AppInfo] = []
    for app_path in found_apps:
        app_info = inspect_app_bundle(
            app_path,
            source_file=dmg,
            source_type="dmg",
            temp_dir=temp_dir,
        )
        results.append(app_info)

    if not results:
        # Clean up temp dir if nothing was found
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(
            f"Could not extract any .app bundles from '{dmg.name}'.\n"
            "Tip: Ensure 7-Zip ('p7zip-full') or Darling is available to extract compressed DMG images."
        )

    return results


# ==============================================================================
# PKG Extraction & Handling
# ==============================================================================

def extract_pkg_xar_python(pkg_path: pathlib.Path, target_dir: pathlib.Path) -> List[pathlib.Path]:
    """
    Pure Python XAR (.pkg) unpacker:
    Extracts the Payload archive(s) and unpacks them using `/usr/bin/cpio` or python.
    """
    try:
        with open(pkg_path, "rb") as f:
            header = f.read(28)
            if len(header) < 28:
                return []
            magic, hdr_size, version, toc_len_comp, toc_len_uncomp, cksum = struct.unpack(
                ">4sHHQQI", header
            )
            if magic != b"xar!":
                logger.debug("PKG is not XAR archive (magic != 'xar!')")
                return []

            toc_comp = f.read(toc_len_comp)
            toc_xml = zlib.decompress(toc_comp)
            root = ET.fromstring(toc_xml)

            heap_start = hdr_size + toc_len_comp

            # Find all Payload files
            found_apps: List[pathlib.Path] = []
            for file_elem in root.iter("file"):
                name_elem = file_elem.find("name")
                if name_elem is None or not name_elem.text:
                    continue
                filename = name_elem.text

                if "Payload" in filename:
                    data_elem = file_elem.find("data")
                    if data_elem is None:
                        continue
                    offset = int(data_elem.find("offset").text or "0")
                    length = int(data_elem.find("length").text or "0")
                    encoding_elem = data_elem.find("encoding")
                    encoding = (
                        encoding_elem.attrib.get("style", "")
                        if encoding_elem is not None
                        else ""
                    )

                    f.seek(heap_start + offset)
                    payload_bytes = f.read(length)

                    # Decompress payload
                    if "gzip" in encoding or payload_bytes[:2] == b"\x1f\x8b":
                        try:
                            payload_decomp = gzip.decompress(payload_bytes)
                        except Exception:
                            payload_decomp = payload_bytes
                    elif "bzip2" in encoding:
                        import bz2
                        try:
                            payload_decomp = bz2.decompress(payload_bytes)
                        except Exception:
                            payload_decomp = payload_bytes
                    else:
                        try:
                            payload_decomp = zlib.decompress(payload_bytes)
                        except Exception:
                            payload_decomp = payload_bytes

                    # Unpack with cpio
                    cpio_bin = shutil.which("cpio") or "/usr/bin/cpio"
                    if os.path.exists(cpio_bin):
                        subprocess.run(
                            [cpio_bin, "-idmu", "--quiet"],
                            input=payload_decomp,
                            cwd=str(target_dir),
                            capture_output=True,
                            timeout=60,
                        )

            # Search extracted target_dir for any .app bundle
            for root_dir, dirs, files in os.walk(target_dir):
                for d in dirs:
                    if d.endswith(".app"):
                        found_apps.append(pathlib.Path(root_dir) / d)

            return found_apps
    except Exception as e:
        logger.warning("Pure Python XAR extraction error: %s", e)
        return []


def inspect_and_extract_pkg(pkg_path: Union[str, pathlib.Path]) -> List[AppInfo]:
    """Inspects a `.pkg` installer file and extracts any embedded .app bundles."""
    pkg = pathlib.Path(pkg_path).resolve()
    temp_dir = tempfile.mkdtemp(prefix="darling_pkg_")
    target_dir = pathlib.Path(temp_dir)

    found_apps = extract_pkg_xar_python(pkg, target_dir)

    # Fallback to 7z if python extractor didn't find .app
    if not found_apps:
        found_apps = extract_dmg_with_7z(pkg, target_dir)

    results: List[AppInfo] = []
    for app_path in found_apps:
        app_info = inspect_app_bundle(
            app_path,
            source_file=pkg,
            source_type="pkg",
            temp_dir=temp_dir,
        )
        results.append(app_info)

    if not results:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(
            f"Could not extract any .app bundles from package '{pkg.name}'."
        )

    return results


def inspect_target(target_path: Union[str, pathlib.Path]) -> List[AppInfo]:
    """
    Universal inspector for `.app`, `.dmg`, or `.pkg` files and directories.
    """
    p = pathlib.Path(target_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Path does not exist: {p}")

    if p.is_dir() and p.name.endswith(".app"):
        return [inspect_app_bundle(p, source_file=p, source_type="app")]

    suffix = p.suffix.lower()
    if suffix == ".dmg":
        return inspect_and_extract_dmg(p)
    elif suffix == ".pkg":
        return inspect_and_extract_pkg(p)
    elif suffix == ".app":
        return [inspect_app_bundle(p, source_file=p, source_type="app")]
    else:
        # Check if it's a directory containing an .app
        if p.is_dir():
            apps: List[AppInfo] = []
            for item in p.glob("*.app"):
                apps.append(inspect_app_bundle(item, source_file=p, source_type="app"))
            if apps:
                return apps

        raise ValueError(
            f"Unsupported file format '{p.name}'. Supported formats: .app, .dmg, .pkg"
        )


# ==============================================================================
# Installation, Desktop Integration & Management
# ==============================================================================

def install_app(
    app_info: AppInfo,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> Tuple[bool, str]:
    """
    Installs the inspected application into Darling prefix:
    - Copies .app bundle to `~/.darling/Applications/<AppName>.app`
    - Preserves file permissions and symlinks
    - Installs high-resolution icons to `~/.local/share/icons/hicolor/<res>x<res>/apps/`
    - Creates standard FreeDesktop .desktop file in `~/.local/share/applications/`
    - Updates icon cache & desktop database
    """
    try:
        if progress_callback:
            progress_callback("Preparing Darling prefix...", 0.1)

        darling_prefix = get_darling_prefix()
        apps_dir = get_darling_applications_dir()
        apps_dir.mkdir(parents=True, exist_ok=True)

        source_bundle = pathlib.Path(app_info.bundle_path)
        dest_bundle = apps_dir / source_bundle.name

        if progress_callback:
            progress_callback(f"Copying {source_bundle.name} to Darling Applications...", 0.3)

        # Remove existing if reinstalling
        if dest_bundle.exists():
            if dest_bundle.is_dir():
                shutil.rmtree(dest_bundle)
            else:
                dest_bundle.unlink()

        # Copy bundle preserving symlinks and permissions
        shutil.copytree(source_bundle, dest_bundle, symlinks=True)

        if progress_callback:
            progress_callback("Installing application icons...", 0.6)

        # Install icons to FreeDesktop hicolor directory
        desktop_id = f"darling-{app_info.bundle_id}"
        hicolor_base = pathlib.Path("~/.local/share/icons/hicolor").expanduser()

        # Generate / copy icons for standard sizes
        icon_resolutions = app_info.icon_resolutions or extract_app_icons(dest_bundle)
        for res, icon_src in icon_resolutions.items():
            res_dir = hicolor_base / f"{res}x{res}" / "apps"
            res_dir.mkdir(parents=True, exist_ok=True)
            dest_icon = res_dir / f"{desktop_id}.png"
            shutil.copy2(icon_src, dest_icon)

        if progress_callback:
            progress_callback("Generating GNOME desktop integration shortcut...", 0.8)

        # Create FreeDesktop .desktop file
        desktop_dir = pathlib.Path("~/.local/share/applications").expanduser()
        desktop_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = desktop_dir / f"{desktop_id}.desktop"

        # Determine exec command for Darling
        # We invoke darling launch or darling shell open
        exec_cmd = f'darling launch "/Applications/{dest_bundle.name}"'

        desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={app_info.display_name}
GenericName=macOS Application
Comment={app_info.bundle_name} (via Darling)
Exec={exec_cmd}
Icon={desktop_id}
Terminal=false
Categories=Utility;macOS;
StartupNotify=false
StartupWMClass={app_info.executable_name or app_info.bundle_name}
X-Darling-BundleID={app_info.bundle_id}
X-Darling-Path=/Applications/{dest_bundle.name}
X-Darling-Arch={','.join(app_info.architectures)}
"""
        desktop_file.write_text(desktop_content, encoding="utf-8")
        desktop_file.chmod(0o755)

        if progress_callback:
            progress_callback("Updating desktop database and icon caches...", 0.95)

        # Refresh caches
        try:
            if shutil.which("update-desktop-database"):
                subprocess.run(
                    ["update-desktop-database", str(desktop_dir)],
                    capture_output=True,
                    timeout=5,
                )
            if shutil.which("gtk-update-icon-cache"):
                subprocess.run(
                    ["gtk-update-icon-cache", "-q", "-t", "-f", str(hicolor_base)],
                    capture_output=True,
                    timeout=5,
                )
        except Exception:
            pass

        # Update app_info state
        app_info.is_installed = True
        app_info.installed_path = str(dest_bundle)
        app_info.desktop_file_path = str(desktop_file)

        if progress_callback:
            progress_callback("Installation complete!", 1.0)

        return True, f"Successfully installed '{app_info.display_name}' into Darling."
    except Exception as e:
        logger.error("Failed to install app %s: %s", app_info.display_name, e, exc_info=True)
        return False, f"Installation failed: {e}"


def uninstall_app(app_info_or_name: Union[AppInfo, str]) -> Tuple[bool, str]:
    """
    Uninstalls an application:
    - Removes `.app` bundle from `~/.darling/Applications/`
    - Removes `.desktop` shortcut
    - Removes icons from `~/.local/share/icons/hicolor/`
    - Refreshes desktop database and icon caches
    """
    try:
        apps_dir = get_darling_applications_dir()
        desktop_dir = pathlib.Path("~/.local/share/applications").expanduser()
        hicolor_base = pathlib.Path("~/.local/share/icons/hicolor").expanduser()

        bundle_name = ""
        bundle_id = ""

        if isinstance(app_info_or_name, AppInfo):
            bundle_name = pathlib.Path(app_info_or_name.bundle_path).name
            bundle_id = app_info_or_name.bundle_id
            if app_info_or_name.installed_path and os.path.exists(app_info_or_name.installed_path):
                app_bundle_path = pathlib.Path(app_info_or_name.installed_path)
            else:
                app_bundle_path = apps_dir / bundle_name
        else:
            bundle_name = app_info_or_name
            if not bundle_name.endswith(".app"):
                bundle_name = f"{bundle_name}.app"
            app_bundle_path = apps_dir / bundle_name

        if not bundle_id and app_bundle_path.is_dir():
            try:
                info = inspect_app_bundle(app_bundle_path)
                bundle_id = info.bundle_id
            except Exception:
                bundle_id = app_bundle_path.stem.lower()

        # Helper for removing files with read-only permissions
        def _force_rm(func, path, exc_info):
            try:
                os.chmod(path, 0o777)
                func(path)
            except Exception:
                pass

        # 1. Remove app bundle from Applications directory
        for target in [app_bundle_path, apps_dir / bundle_name]:
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target, onerror=_force_rm)
                else:
                    target.unlink()

        # 2. Remove desktop shortcut
        desktop_id = f"darling-{bundle_id}"
        desktop_file = desktop_dir / f"{desktop_id}.desktop"
        if desktop_file.is_file():
            desktop_file.unlink()

        if isinstance(app_info_or_name, AppInfo) and app_info_or_name.desktop_file_path:
            p = pathlib.Path(app_info_or_name.desktop_file_path)
            if p.is_file():
                p.unlink()

        # Also search for any desktop file containing this bundle
        for df in desktop_dir.glob("darling-*.desktop"):
            try:
                content = df.read_text(errors="ignore")
                if bundle_name in content or (bundle_id and bundle_id in content):
                    df.unlink()
            except Exception:
                pass

        # 3. Remove icons
        for res in [512, 256, 128, 64, 32]:
            for did in [desktop_id, bundle_id, bundle_name]:
                icon_file = hicolor_base / f"{res}x{res}" / "apps" / f"{did}.png"
                if icon_file.is_file():
                    icon_file.unlink()

        # 4. Refresh caches
        try:
            if shutil.which("update-desktop-database"):
                subprocess.run(
                    ["update-desktop-database", str(desktop_dir)],
                    capture_output=True,
                    timeout=5,
                )
            if shutil.which("gtk-update-icon-cache"):
                subprocess.run(
                    ["gtk-update-icon-cache", "-q", "-t", "-f", str(hicolor_base)],
                    capture_output=True,
                    timeout=5,
                )
        except Exception:
            pass

        # Update app_info object if passed
        if isinstance(app_info_or_name, AppInfo):
            app_info_or_name.is_installed = False
            app_info_or_name.installed_path = None
            app_info_or_name.desktop_file_path = None

        return True, f"Successfully uninstalled '{bundle_name}'."
    except Exception as e:
        logger.error("Uninstall error: %s", e)
        return False, f"Uninstall failed: {e}"


def list_installed_apps() -> List[AppInfo]:
    """Lists all macOS applications installed in the Darling prefix."""
    apps_dir = get_darling_applications_dir()
    installed: List[AppInfo] = []

    if not apps_dir.is_dir():
        return installed

    for item in sorted(apps_dir.glob("*.app")):
        if item.is_dir():
            try:
                info = inspect_app_bundle(item, source_file=item, source_type="app")
                installed.append(info)
            except Exception as e:
                logger.warning("Failed inspecting installed app %s: %s", item, e)

    return installed


def initialize_anything_mac_runtime() -> Tuple[bool, str]:
    """Initializes the Darling runtime and prefix."""
    if anything_mac_runtime:
        return anything_mac_runtime.initialize_prefix()
    prefix = get_darling_prefix()
    prefix.mkdir(parents=True, exist_ok=True)
    return True, f"Prefix created at {prefix}"


def launch_app(app_info: Union[AppInfo, str], method: str = "auto") -> Tuple[bool, str]:
    """
    Launches an application inside Darling using tiered runtime execution:
    1. Native Darling or anything_mac_runtime
    2. Darling CLI direct execution
    """
    bundle_name = ""
    bundle_id = ""
    bundle_path = ""
    archs: List[str] = []

    if isinstance(app_info, AppInfo):
        bundle_name = pathlib.Path(app_info.bundle_path).name
        bundle_id = app_info.bundle_id
        bundle_path = app_info.bundle_path
        archs = app_info.architectures or []
    else:
        bundle_name = pathlib.Path(app_info).name
        if not bundle_name.endswith(".app"):
            bundle_name = f"{bundle_name}.app"
        bundle_path = str(get_darling_prefix() / "Applications" / bundle_name)

    # Architecture compatibility check
    if not archs:
        try:
            target_p = pathlib.Path(bundle_path)
            if not target_p.exists() and bundle_name:
                target_p = get_darling_prefix() / "Applications" / bundle_name
            exe = find_executable_in_bundle(target_p)
            if exe:
                archs = parse_macho_architectures(exe)
        except Exception:
            pass

    import platform
    host_arch = platform.machine()
    if host_arch == "x86_64" and archs and "x86_64" not in archs and "i386" not in archs:
        return (
            False,
            f"Cannot launch '{bundle_name}': compiled for Apple Silicon (ARM64 only). "
            f"Your computer has an Intel/AMD (x86_64) processor. "
            f"Darling runs macOS apps natively on your processor without CPU emulation. "
            f"Please download the Intel (x86_64) or Universal version."
        )

    # Minimum macOS version check
    min_os = ""
    if isinstance(app_info, AppInfo):
        min_os = app_info.min_os_version
    else:
        try:
            target_p = pathlib.Path(bundle_path)
            if not target_p.exists() and bundle_name:
                target_p = get_darling_prefix() / "Applications" / bundle_name
            pinfo = inspect_app_bundle(target_p)
            min_os = pinfo.min_os_version
        except Exception:
            pass

    # The minimum deployment target alone cannot prove API incompatibility.
    # Allow the runtime to try; dyld will report any actually missing symbols.

    # 1. Try launching through anything_mac_runtime
    if anything_mac_runtime:
        try:
            res = anything_mac_runtime.launch_app(bundle_path, require_gui=True)
            if res.success:
                return True, res.message
            if res.tier_used == anything_mac_runtime.RuntimeTier.DARLING_ROOTLESS:
                return False, res.message
        except Exception as e:
            logger.warning("anything_mac_runtime launch attempt: %s", e)

    # 2. Try darling binary fallback
    darling_bin = shutil.which("darling")
    if not darling_bin:
        for p in [
            os.path.expanduser("~/.local/bin/darling"),
            os.path.expanduser("~/.local/darling/usr/bin/darling"),
            "/usr/local/bin/darling",
            "/usr/bin/darling",
            "/opt/darling/bin/darling",
        ]:
            if os.path.exists(p) and os.access(p, os.X_OK):
                darling_bin = p
                break

    if not darling_bin:
        return False, "Darling runtime executable was not found. Please install Darling or run prefix setup."

    container_app_path = f"/Applications/{bundle_name}"

    try:
        if method == "darling shell open":
            cmd = [darling_bin, "shell", "open", "-a", container_app_path]
        elif method == "darling launch id" and bundle_id:
            cmd = [darling_bin, "shell", "open", "-b", bundle_id]
        else:
            cmd = [darling_bin, "shell", "open", "-a", container_app_path]

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True, f"Launched '{bundle_name}' via '{' '.join(cmd)}'."
    except Exception as e:
        logger.error("Failed to launch %s: %s", bundle_name, e)
        return False, f"Failed to launch application: {e}"


def get_darling_status() -> Dict[str, Any]:
    """Inspects AnythingMac prefix, runtime, and system status."""
    darling_bin = (
        shutil.which("anything-mac")
        or shutil.which("amac")
        or shutil.which("darling")
    )
    if not darling_bin:
        for p in [
            os.path.expanduser("~/.local/bin/anything-mac"),
            os.path.expanduser("~/.local/bin/amac"),
            os.path.expanduser("~/.local/bin/darling"),
            os.path.expanduser("~/.local/anything-mac/usr/bin/darling"),
            os.path.expanduser("~/.local/darling/usr/bin/darling"),
            "/usr/local/bin/anything-mac",
            "/usr/bin/anything-mac",
            "/usr/local/bin/darling",
            "/usr/bin/darling",
        ]:
            if os.path.exists(p) and os.access(p, os.X_OK):
                darling_bin = p
                break

    prefix = get_darling_prefix()
    prefix_exists = prefix.is_dir()

    # Container status
    sock1 = prefix / ".anythingmacserver.sock"
    sock2 = prefix / ".darlingserver.sock"
    container_active = sock1.exists() or sock2.exists()

    # Tahoe shim status
    shim_path = prefix / "usr/lib/libanything_mac_tahoe_shim.dylib"
    has_tahoe_shim = shim_path.exists()

    prefix_size = 0
    if prefix_exists:
        try:
            # Quick stat on prefix
            for root, dirs, files in os.walk(prefix):
                for f in files:
                    fp = os.path.join(root, f)
                    if not os.path.islink(fp):
                        prefix_size += os.path.getsize(fp)
        except Exception:
            pass

    # Check kernel module or mach dev
    mach_dev_exists = os.path.exists("/dev/mach") or os.path.exists("/dev/darling-mach")

    # Darling version
    darling_version = "Unknown"
    if darling_bin:
        try:
            res = subprocess.run([darling_bin, "--version"], capture_output=True, text=True, timeout=3)
            darling_version = res.stdout.strip() or res.stderr.strip() or "Found"
        except Exception:
            darling_version = "Installed"

    import platform
    host_arch = platform.machine()

    status_data = {
        "darling_binary": darling_bin,
        "darling_installed": bool(darling_bin),
        "darling_version": darling_version,
        "prefix_path": str(prefix),
        "prefix_exists": prefix_exists,
        "prefix_size_formatted": format_size(prefix_size),
        "mach_dev_exists": mach_dev_exists,
        "container_active": container_active,
        "has_tahoe_shim": has_tahoe_shim,
        "tahoe_version": "16.0 (Tahoe)",
        "host_architecture": host_arch,
        "is_host_x86_64": host_arch in ("x86_64", "AMD64"),
    }

    if anything_mac_runtime:
        try:
            rt_status = anything_mac_runtime.get_full_runtime_status()
            status_data["runtime_tiers"] = rt_status.get("runtime_tiers", [])
            status_data["best_tier_gui"] = rt_status.get("best_tier_gui", "unavailable")
            status_data["prefix_initialized"] = rt_status.get("prefix_initialized", False)
        except Exception as e:
            logger.warning("Error fetching full runtime status: %s", e)

    return status_data
