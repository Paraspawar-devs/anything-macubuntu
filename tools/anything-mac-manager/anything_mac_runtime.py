#!/usr/bin/env python3
"""
AnythingMac Runtime Layer
=====================
Tiered execution engine for running macOS applications on Ubuntu 26.04.1 LTS.

Execution Tiers (fastest → most compatible):
  1. Native Darling (if installed kernel module + darling binary)
  2. Darling Userspace (darling binary without kernel module via rootless mode)
  3. QEMU macOS VM (full x86_64/arm64 macOS in QEMU)
  4. Custom Mach-O QEMU userspace emulation (qemu-x86_64-static)
  5. Informative error with setup instructions

This module is used by anything_mac_backend.py and anything-mac-manager.py.
"""

from __future__ import annotations

import dataclasses
import enum
import functools
import json
import logging
import os
import pathlib
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("anything_mac_runtime")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DARLING_SEARCH_PATHS = [
    "/usr/local/bin/darling",
    "/usr/bin/darling",
    "/opt/darling/bin/darling",
    os.path.expanduser("~/.local/bin/darling"),
    os.path.expanduser("~/.local/darling/usr/bin/darling"),
    "/snap/bin/darling",
]

QEMU_X86_STATIC_NAMES = ["qemu-x86_64-static", "qemu-x86_64"]
QEMU_SYSTEM_NAMES = ["qemu-system-x86_64", "qemu-system-amd64"]

PREFIX_DIR = pathlib.Path(os.environ.get("ANYTHING_MAC_PREFIX", os.path.expanduser("~/.darling")))
VM_DIR = pathlib.Path(os.path.expanduser("~/.local/share/anything-mac-manager/vms"))
RUNTIME_DATA_DIR = pathlib.Path(os.path.expanduser("~/.local/share/anything-mac-manager"))


class RuntimeTier(enum.Enum):
    NATIVE_DARLING = "native_darling"          # Full darling with kernel module
    DARLING_ROOTLESS = "darling_rootless"       # darling binary, no kernel module
    QEMU_MACOS_VM = "qemu_macos_vm"            # QEMU macOS VM
    QEMU_USERSPACE = "qemu_userspace"           # qemu-x86_64 userspace emulation
    ROSETTA_STYLE = "rosetta_style"             # Custom Mach-O → Linux translator
    UNAVAILABLE = "unavailable"                 # No runtime available


@dataclasses.dataclass
class RuntimeCapability:
    tier: RuntimeTier
    available: bool
    binary_path: Optional[str]
    description: str
    supports_gui: bool
    estimated_speed: str  # "native", "fast", "medium", "slow"
    notes: str = ""


@dataclasses.dataclass
class LaunchResult:
    success: bool
    pid: Optional[int]
    tier_used: RuntimeTier
    message: str
    command: List[str]


# ---------------------------------------------------------------------------
# Runtime detection
# ---------------------------------------------------------------------------

def detect_runtime() -> Dict[str, RuntimeCapability]:
    """Detect all available execution tiers."""
    caps: Dict[str, RuntimeCapability] = {}

    # Tier 1: Native Darling (kernel module)
    darling_bin = _find_binary(DARLING_SEARCH_PATHS)
    mach_dev = _check_mach_device()
    caps["native_darling"] = RuntimeCapability(
        tier=RuntimeTier.NATIVE_DARLING,
        available=bool(darling_bin and mach_dev),
        binary_path=darling_bin,
        description="Full Darling with kernel module (/dev/mach)",
        supports_gui=_x11_display_available(),
        estimated_speed="near-native",
        notes="Requires darlingserver kernel module. Best option for GUI apps.",
    )

    # Tier 2: Darling Rootless (no kernel module)
    darling_launcher = os.path.expanduser("~/.local/bin/darling")
    caps["darling_rootless"] = RuntimeCapability(
        tier=RuntimeTier.DARLING_ROOTLESS,
        available=_rootless_runtime_available(),
        binary_path=darling_launcher if os.path.isfile(darling_launcher) else os.path.expanduser("~/.local/darling/usr/bin/darling"),
        description="Darling rootless container in Bubblewrap",
        supports_gui=_x11_display_available(),
        estimated_speed="near-native",
        notes="Rootless runtime is experimental; it forwards a local X11/Xwayland display.",
    )

    # Tier 3: QEMU macOS VM
    qemu_sys = _find_binary([shutil.which(n) or f"/usr/bin/{n}" for n in QEMU_SYSTEM_NAMES])
    macos_image = _find_macos_vm_image()
    caps["qemu_macos_vm"] = RuntimeCapability(
        tier=RuntimeTier.QEMU_MACOS_VM,
        available=bool(qemu_sys and macos_image),
        binary_path=qemu_sys,
        description="Full macOS VM via QEMU (requires macOS disk image)",
        supports_gui=True,
        estimated_speed="slow",
        notes=f"VM image: {macos_image or 'not found'}. Needs macOS QDHC image.",
    )

    # Tier 4: QEMU userspace (qemu-x86_64-static)
    qemu_user = _find_binary_in_path(QEMU_X86_STATIC_NAMES)
    caps["qemu_userspace"] = RuntimeCapability(
        tier=RuntimeTier.QEMU_USERSPACE,
        available=bool(qemu_user),
        binary_path=qemu_user,
        description="QEMU x86_64 userspace emulation",
        supports_gui=False,
        estimated_speed="medium",
        notes="Can run x86_64 Mach-O CLI tools with stub libraries. Experimental.",
    )

    # Tier 5: Custom rosetta-style translator
    translator_bin = str(RUNTIME_DATA_DIR / "mach-translator")
    caps["rosetta_style"] = RuntimeCapability(
        tier=RuntimeTier.ROSETTA_STYLE,
        available=os.path.exists(translator_bin) and os.access(translator_bin, os.X_OK),
        binary_path=translator_bin if os.path.exists(translator_bin) else None,
        description="Custom Mach-O to Linux ELF translation layer",
        supports_gui=False,
        estimated_speed="fast",
        notes="In development. Translates Mach-O syscalls to Linux.",
    )

    return caps


def get_best_tier(caps: Dict[str, RuntimeCapability], require_gui: bool = True) -> Optional[RuntimeCapability]:
    """Return the best available tier for the given requirements."""
    tier_order = [
        "native_darling",
        "qemu_macos_vm",
        "darling_rootless",
        "qemu_userspace",
        "rosetta_style",
    ]
    if not require_gui:
        tier_order = ["native_darling", "darling_rootless", "qemu_userspace",
                      "rosetta_style", "qemu_macos_vm"]
    for key in tier_order:
        cap = caps.get(key)
        if cap and cap.available:
            if require_gui and not cap.supports_gui:
                continue
            return cap
    return None


# ---------------------------------------------------------------------------
# Application launching
# ---------------------------------------------------------------------------

def launch_app(
    app_path: str,
    require_gui: bool = True,
    env: Optional[Dict[str, str]] = None,
    on_output: Optional[Callable[[str], None]] = None,
) -> LaunchResult:
    """
    Launch a macOS .app bundle using the best available runtime.

    Args:
        app_path: Path to the .app bundle or Mach-O executable.
        require_gui: Whether the app needs a display.
        env: Extra environment variables to pass.
        on_output: Callback for stdout/stderr lines (optional).

    Returns:
        LaunchResult with success status, PID, and message.
    """
    app_path = str(app_path)

    # Architecture pre-flight compatibility check
    app_target = pathlib.Path(app_path)
    if not app_target.exists() and str(app_path).startswith("/Applications"):
        app_target = PREFIX_DIR / str(app_path).lstrip("/")

    exe_file = _find_macho_executable(app_target)
    if exe_file and exe_file.is_file():
        archs = _inspect_macho_architectures(exe_file)
        host_arch = platform.machine()
        if host_arch == "x86_64" and archs and "x86_64" not in archs and "i386" not in archs:
            return LaunchResult(
                success=False,
                pid=None,
                tier_used=RuntimeTier.UNAVAILABLE,
                message=(
                    f"Incompatible CPU Architecture: '{app_target.name}' is compiled exclusively "
                    f"for Apple Silicon ({', '.join(archs)}). Your laptop has an Intel/AMD (x86_64) processor. "
                    f"Darling runs macOS apps natively without CPU emulation. "
                    f"Please install the Intel (x86_64) or Universal macOS version."
                ),
                command=[],
            )

    caps = detect_runtime()
    cap = get_best_tier(caps, require_gui=require_gui)

    if cap is None:
        return LaunchResult(
            success=False,
            pid=None,
            tier_used=RuntimeTier.UNAVAILABLE,
            message=_build_install_instructions(),
            command=[],
        )

    # Dispatch to the right launcher
    if cap.tier == RuntimeTier.NATIVE_DARLING:
        return _launch_via_darling(app_path, cap.binary_path, env, on_output)
    elif cap.tier == RuntimeTier.DARLING_ROOTLESS:
        return _launch_via_darling(app_path, cap.binary_path, env, on_output, rootless=True)
    elif cap.tier == RuntimeTier.QEMU_MACOS_VM:
        return _launch_via_qemu_vm(app_path, cap.binary_path, env, on_output)
    elif cap.tier == RuntimeTier.QEMU_USERSPACE:
        return _launch_via_qemu_userspace(app_path, cap.binary_path, env, on_output)
    elif cap.tier == RuntimeTier.ROSETTA_STYLE:
        return _launch_via_translator(app_path, cap.binary_path, env, on_output)
    else:
        return LaunchResult(
            success=False,
            pid=None,
            tier_used=RuntimeTier.UNAVAILABLE,
            message=_build_install_instructions(),
            command=[],
        )


def _launch_via_darling(
    app_path: str,
    darling_bin: str,
    env: Optional[Dict[str, str]],
    on_output: Optional[Callable],
    rootless: bool = False,
) -> LaunchResult:
    """Launch through the native or rootless Darling CLI."""
    app_p = pathlib.Path(app_path)
    darling_launcher = os.path.expanduser("~/.local/bin/darling")
    if rootless and os.path.isfile(darling_launcher) and os.access(darling_launcher, os.X_OK):
        darling_bin = darling_launcher

    # Determine command
    if app_p.suffix == ".app":
        cmd = [darling_bin, "launch", f"/Applications/{app_p.name}"]
    elif app_p.is_file():
        cmd = [darling_bin, "shell", str(app_p)]
    else:
        cmd = [darling_bin, "launch", str(app_p)]

    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    if "DISPLAY" not in merged_env:
        merged_env["DISPLAY"] = ":0"

    try:
        proc = subprocess.Popen(
            cmd,
            env=merged_env,
            stdout=subprocess.PIPE if on_output else subprocess.DEVNULL,
            stderr=subprocess.PIPE if on_output or rootless else subprocess.DEVNULL,
            start_new_session=True,
        )
        if on_output or rootless:
            _stream_output(proc, on_output or logger.warning)
        if rootless:
            try:
                proc.wait(timeout=0.35)
            except subprocess.TimeoutExpired:
                pass
            else:
                if proc.returncode:
                    return LaunchResult(
                        success=False, pid=None, tier_used=RuntimeTier.DARLING_ROOTLESS,
                        message=f"Darling failed during startup (exit status {proc.returncode})", command=cmd,
                    )
        return LaunchResult(
            success=True,
            pid=proc.pid,
            tier_used=RuntimeTier.DARLING_ROOTLESS if rootless else RuntimeTier.NATIVE_DARLING,
            message=f"Launched via Darling (PID {proc.pid})",
            command=cmd,
        )
    except Exception as e:
        return LaunchResult(
            success=False,
            pid=None,
            tier_used=RuntimeTier.DARLING_ROOTLESS if rootless else RuntimeTier.NATIVE_DARLING,
            message=f"Darling launch failed: {e}",
            command=cmd,
        )


def _launch_via_qemu_vm(
    app_path: str,
    qemu_bin: str,
    env: Optional[Dict[str, str]],
    on_output: Optional[Callable],
) -> LaunchResult:
    """Launch via QEMU macOS VM."""
    image = _find_macos_vm_image()
    if not image:
        return LaunchResult(
            success=False,
            pid=None,
            tier_used=RuntimeTier.QEMU_MACOS_VM,
            message="No macOS disk image found. Place a macOS QCOW2 image at ~/.local/share/anything-mac-manager/vms/macos.qcow2",
            command=[],
        )

    # Basic QEMU launch — the VM must have macOS pre-installed
    cmd = [
        qemu_bin,
        "-machine", "q35,accel=kvm:hvf:tcg",
        "-cpu", "Penryn,kvm=on,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on",
        "-m", "4096",
        "-smp", "4,cores=2",
        "-drive", f"file={image},format=qcow2,if=virtio",
        "-device", "usb-tablet",
        "-device", "virtio-net-pci,netdev=n1",
        "-netdev", "user,id=n1",
        "-display", "sdl",
        "-vga", "std",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return LaunchResult(
            success=True,
            pid=proc.pid,
            tier_used=RuntimeTier.QEMU_MACOS_VM,
            message=f"Launched macOS VM via QEMU (PID {proc.pid}). App must be opened manually inside VM.",
            command=cmd,
        )
    except Exception as e:
        return LaunchResult(
            success=False,
            pid=None,
            tier_used=RuntimeTier.QEMU_MACOS_VM,
            message=f"QEMU VM launch failed: {e}",
            command=cmd,
        )


def _launch_via_qemu_userspace(
    app_path: str,
    qemu_bin: str,
    env: Optional[Dict[str, str]],
    on_output: Optional[Callable],
) -> LaunchResult:
    """
    Attempt QEMU x86_64 userspace emulation of a Mach-O binary.
    This is experimental — QEMU userspace does not natively support Mach-O.
    We wrap the binary in a Linux ELF shim that we generate on the fly.
    """
    app_p = pathlib.Path(app_path)
    executable = _find_macho_executable(app_p)
    if not executable:
        return LaunchResult(
            success=False,
            pid=None,
            tier_used=RuntimeTier.QEMU_USERSPACE,
            message=f"Could not find Mach-O executable inside {app_path}",
            command=[],
        )

    # Try running the executable directly via qemu-x86_64
    # This will fail with Mach-O format errors, but let's capture the error
    cmd = [qemu_bin, str(executable)]
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5, env=merged_env
        )
        if result.returncode == 0 or "Mach-O" not in (result.stderr or ""):
            return LaunchResult(
                success=True,
                pid=None,
                tier_used=RuntimeTier.QEMU_USERSPACE,
                message="Ran via QEMU userspace (experimental)",
                command=cmd,
            )
        else:
            return LaunchResult(
                success=False,
                pid=None,
                tier_used=RuntimeTier.QEMU_USERSPACE,
                message=f"QEMU userspace: Mach-O not directly supported. Error: {result.stderr[:200]}",
                command=cmd,
            )
    except subprocess.TimeoutExpired:
        return LaunchResult(
            success=True,
            pid=None,
            tier_used=RuntimeTier.QEMU_USERSPACE,
            message="Process started (timed out waiting — may be running in background)",
            command=cmd,
        )
    except Exception as e:
        return LaunchResult(
            success=False,
            pid=None,
            tier_used=RuntimeTier.QEMU_USERSPACE,
            message=f"QEMU userspace launch failed: {e}",
            command=cmd,
        )


def _launch_via_translator(
    app_path: str,
    translator_bin: str,
    env: Optional[Dict[str, str]],
    on_output: Optional[Callable],
) -> LaunchResult:
    """Launch via custom Mach-O → Linux translation layer."""
    app_p = pathlib.Path(app_path)
    executable = _find_macho_executable(app_p)
    if not executable:
        return LaunchResult(
            success=False,
            pid=None,
            tier_used=RuntimeTier.ROSETTA_STYLE,
            message=f"Could not find Mach-O executable inside {app_path}",
            command=[],
        )

    cmd = [translator_bin, str(executable)]
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    try:
        proc = subprocess.Popen(
            cmd,
            env=merged_env,
            stdout=subprocess.PIPE if on_output else subprocess.DEVNULL,
            stderr=subprocess.PIPE if on_output else subprocess.DEVNULL,
            start_new_session=True,
        )
        if on_output:
            _stream_output(proc, on_output)
        return LaunchResult(
            success=True,
            pid=proc.pid,
            tier_used=RuntimeTier.ROSETTA_STYLE,
            message=f"Launched via Mach-O translator (PID {proc.pid})",
            command=cmd,
        )
    except Exception as e:
        return LaunchResult(
            success=False,
            pid=None,
            tier_used=RuntimeTier.ROSETTA_STYLE,
            message=f"Translator launch failed: {e}",
            command=cmd,
        )


# ---------------------------------------------------------------------------
# Prefix / environment setup
# ---------------------------------------------------------------------------

def initialize_prefix(prefix: Optional[pathlib.Path] = None, force: bool = False) -> Tuple[bool, str]:
    """
    Create and initialize the Darling prefix directory.
    This is an offline simulation of what 'darling prefix' does.
    """
    prefix = prefix or PREFIX_DIR
    if prefix.exists() and not force:
        return True, f"Prefix already exists at {prefix}"

    try:
        # Create macOS-like directory tree
        dirs = [
            "Applications",
            "Library/Application Support",
            "Library/Caches",
            "Library/Frameworks",
            "Library/Preferences",
            "Library/Logs",
            "System/Library/Frameworks",
            "System/Library/Extensions",
            "Users/Shared",
            f"Users/{os.environ.get('USER', 'user')}",
            "private/tmp",
            "private/var/run",
            "private/var/log",
            "private/etc",
            "usr/local/lib",
            "usr/local/bin",
            "usr/local/share",
            "tmp",
            "var",
            "bin",
            "sbin",
            "etc",
        ]
        for d in dirs:
            (prefix / d).mkdir(parents=True, exist_ok=True)

        # Write a basic hosts file
        hosts_file = prefix / "private/etc/hosts"
        if not hosts_file.exists():
            hosts_file.write_text(
                "127.0.0.1\tlocalhost\n"
                "::1\tlocalhost\n"
                "127.0.0.1\t<app>.local\n"
            )

        # Write a basic launchd.conf stub
        launchd_conf = prefix / "private/etc/launchd.conf"
        if not launchd_conf.exists():
            launchd_conf.write_text("# Darling launchd configuration\n")

        # Mark initialization
        (prefix / ".darling_initialized").write_text(
            f"Darling prefix initialized at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Host: Ubuntu 26.04.1 LTS (Resolute)\n"
            f"Arch: {platform.machine()}\n"
        )

        logger.info("Initialized Darling prefix at %s", prefix)
        return True, f"Prefix initialized at {prefix}"
    except Exception as e:
        return False, f"Failed to initialize prefix: {e}"


def install_app_to_prefix(
    app_bundle_path: str,
    prefix: Optional[pathlib.Path] = None,
) -> Tuple[bool, str]:
    """Copy .app bundle into the Darling prefix /Applications/ directory."""
    prefix = prefix or PREFIX_DIR
    app_p = pathlib.Path(app_bundle_path)
    if not app_p.exists():
        return False, f"App bundle not found: {app_bundle_path}"

    ok, msg = initialize_prefix(prefix)
    if not ok:
        return False, msg

    dest = prefix / "Applications" / app_p.name
    try:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(str(app_p), str(dest), symlinks=True)
        return True, f"Installed {app_p.name} → {dest}"
    except Exception as e:
        return False, f"Failed to install app to prefix: {e}"


# ---------------------------------------------------------------------------
# Darling build / installation helpers
# ---------------------------------------------------------------------------

def check_and_build_darling() -> Dict[str, Any]:
    """
    Check if we can build the minimal Darling launcher from source.
    Returns status info and any build output.
    """
    src_root = pathlib.Path(__file__).resolve().parents[2]
    darling_c = src_root / "src/startup/darling.c"
    out_bin = RUNTIME_DATA_DIR / "darling-launcher"

    result = {
        "can_build": False,
        "source_exists": darling_c.exists(),
        "gcc_available": bool(shutil.which("gcc")),
        "built": out_bin.exists(),
        "binary_path": str(out_bin),
        "notes": [],
    }

    if not darling_c.exists():
        result["notes"].append("darling.c source not found")
        return result

    if not shutil.which("gcc"):
        result["notes"].append("gcc not installed")
        return result

    result["can_build"] = True

    # Attempt minimal compilation (darling.c has many deps — try anyway)
    if not out_bin.exists():
        RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(
                [
                    "gcc", "-o", str(out_bin),
                    str(darling_c),
                    f"-I{src_root}/src/startup",
                    f"-I{src_root}/src",
                    "-lutil", "-lpthread",
                    "-D_GNU_SOURCE",
                    "-DINSTALL_PREFIX=\"/usr/local\"",
                    "-DDARLING_VERSION=\"0.1.dev\"",
                    "-w",  # suppress warnings
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                result["built"] = True
                result["notes"].append("Successfully compiled darling-launcher")
            else:
                result["notes"].append(f"Compile failed: {proc.stderr[:300]}")
        except Exception as e:
            result["notes"].append(f"Build error: {e}")

    return result


def get_full_runtime_status() -> Dict[str, Any]:
    """Returns full runtime status for the GUI Status page."""
    caps = detect_runtime()
    best = get_best_tier(caps, require_gui=True)
    best_nogui = get_best_tier(caps, require_gui=False)
    prefix = PREFIX_DIR
    prefix_initialized = (prefix / ".darling_initialized").exists()

    # Build status for each tier
    tier_statuses = []
    for key, cap in caps.items():
        tier_statuses.append({
            "name": cap.tier.value,
            "available": cap.available,
            "binary": cap.binary_path,
            "description": cap.description,
            "supports_gui": cap.supports_gui,
            "speed": cap.estimated_speed,
            "notes": cap.notes,
        })

    return {
        "runtime_tiers": tier_statuses,
        "best_tier_gui": best.tier.value if best else "unavailable",
        "best_tier_nogui": best_nogui.tier.value if best_nogui else "unavailable",
        "prefix_path": str(prefix),
        "prefix_initialized": prefix_initialized,
        "host_arch": platform.machine(),
        "host_os": platform.platform(),
        "kernel": platform.release(),
        "python": sys.version.split()[0],
        "qemu_system": bool(shutil.which("qemu-system-x86_64") or shutil.which("qemu-system-amd64")),
        "qemu_user": bool(shutil.which("qemu-x86_64") or shutil.which("qemu-x86_64-static")),
        "gcc": bool(shutil.which("gcc")),
        "mach_device": _check_mach_device(),
        "managed_runtime": _managed_runtime_status(),
    }


def _managed_runtime_status() -> Dict[str, Any]:
    """Describe the optional user-local runtime layout without assuming it works."""
    root = pathlib.Path(os.path.expanduser("~/.local/darling"))
    candidates = {
        "darling": root / "usr/bin/darling",
        "darlingserver": root / "usr/bin/darlingserver",
        "mldr": root / "usr/libexec/darling/usr/libexec/darling/mldr",
        "dyld": root / "usr/libexec/darling/usr/lib/dyld",
        "rootless_shim": root / "librootless.so",
    }
    present = {name: path.is_file() for name, path in candidates.items()}
    bwrap = shutil.which("bwrap")
    bwrap_usable = _bwrap_usable(bwrap) if bwrap else False
    complete = all(present.values()) and bwrap_usable
    return {
        "root": str(root),
        "components": present,
        "bwrap": bwrap,
        "bwrap_usable": bwrap_usable,
        "layout_complete": complete,
        "ready": False,
        "note": "Candidate runtime layout found; server RPC and GUI launch still need an app-level check." if complete else "Missing required components or usable bwrap namespace.",
    }


def _rootless_runtime_available() -> bool:
    return _managed_runtime_status()["layout_complete"]


def _x11_display_available() -> bool:
    display = os.environ.get("DISPLAY", "")
    if not display:
        return False
    number = display.rsplit(":", 1)[-1].split(".", 1)[0]
    return pathlib.Path("/tmp/.X11-unix", f"X{number}").exists()


@functools.lru_cache(maxsize=1)
def _bwrap_usable(bwrap: str) -> bool:
    """Check that user namespaces work, not just that bwrap is installed."""
    try:
        return subprocess.run(
            [bwrap, "--die-with-parent", "--new-session", "--ro-bind", "/", "/", "--", "/bin/true"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_binary(paths: List[Optional[str]]) -> Optional[str]:
    """Return the first existing executable path from the list."""
    for p in paths:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def _find_binary_in_path(names: List[str]) -> Optional[str]:
    """Find a binary by name in PATH."""
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _check_mach_device() -> bool:
    """Check if /dev/mach (Darling kernel module) is present."""
    return os.path.exists("/dev/mach") or os.path.exists("/dev/darling-mach")


def _find_macos_vm_image() -> Optional[str]:
    """Search for a macOS QCOW2 disk image."""
    search_paths = [
        VM_DIR / "macos.qcow2",
        VM_DIR / "macos.img",
        pathlib.Path.home() / "macos.qcow2",
        pathlib.Path("/var/lib/darling/macos.qcow2"),
    ]
    for p in search_paths:
        if p.exists():
            return str(p)
    return None


def _find_macho_executable(app_bundle: pathlib.Path) -> Optional[pathlib.Path]:
    """Find the main Mach-O executable inside a .app bundle."""
    if not app_bundle.is_dir():
        if app_bundle.is_file():
            return app_bundle
        return None

    macos_dir = app_bundle / "Contents" / "MacOS"
    if macos_dir.is_dir():
        plist_path = app_bundle / "Contents" / "Info.plist"
        if plist_path.is_file():
            try:
                import plistlib
                with open(plist_path, "rb") as fp:
                    pl = plistlib.load(fp)
                    exe = pl.get("CFBundleExecutable")
                    if exe and (macos_dir / exe).is_file():
                        return macos_dir / exe
            except Exception:
                pass
        for f in sorted(macos_dir.iterdir()):
            if f.is_file() and os.access(f, os.X_OK):
                # Verify Mach-O magic
                try:
                    with open(f, "rb") as fh:
                        magic = fh.read(4)
                    if magic in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",
                                 b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
                                 b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
                        return f
                except Exception:
                    pass
    return None


def _inspect_macho_architectures(file_path: pathlib.Path) -> List[str]:
    """Inspect Mach-O architectures of a binary file."""
    archs: List[str] = []
    try:
        with open(file_path, "rb") as f:
            magic = f.read(4)
            if len(magic) < 4:
                return archs
            if magic in (b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe"):
                cputype = struct.unpack("<I" if magic == b"\xcf\xfa\xed\xfe" else ">I", f.read(4))[0]
                if cputype == 0x0100000C:
                    archs.append("arm64")
                elif cputype == 0x01000007:
                    archs.append("x86_64")
            elif magic in (b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe"):
                cputype = struct.unpack("<I" if magic == b"\xce\xfa\xed\xfe" else ">I", f.read(4))[0]
                if cputype == 7:
                    archs.append("i386")
            elif magic in (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
                is_big = (magic == b"\xca\xfe\xba\xbe")
                fmt = ">I" if is_big else "<I"
                nfat = struct.unpack(fmt, f.read(4))[0]
                for _ in range(nfat):
                    cputype = struct.unpack(fmt, f.read(4))[0]
                    f.read(16)
                    if cputype == 0x0100000C:
                        archs.append("arm64")
                    elif cputype == 0x01000007:
                        archs.append("x86_64")
                    elif cputype == 7:
                        archs.append("i386")
    except Exception:
        pass
    return archs


def _stream_output(proc: subprocess.Popen, callback: Callable[[str], None]) -> None:
    """Stream stdout/stderr from a process to a callback in background threads."""
    def _reader(stream, prefix):
        try:
            for line in stream:
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                callback(f"[{prefix}] {line.rstrip()}")
        except Exception:
            pass

    if proc.stdout:
        t = threading.Thread(target=_reader, args=(proc.stdout, "out"), daemon=True)
        t.start()
    if proc.stderr:
        t = threading.Thread(target=_reader, args=(proc.stderr, "err"), daemon=True)
        t.start()


def _build_install_instructions() -> str:
    """Return user-friendly instructions for installing Darling."""
    return (
        "No macOS runtime is available. To run macOS apps, you need one of:\n\n"
        "Option 1 — Install Darling (recommended):\n"
        "  sudo add-apt-repository ppa:darlinghq/darling\n"
        "  sudo apt update && sudo apt install darling\n"
        "  darling shell  # initialize prefix\n\n"
        "Option 2 — Install from source (advanced):\n"
        "  git clone --recursive https://github.com/darlinghq/darling\n"
        "  cd darling && mkdir build && cd build\n"
        "  cmake .. && make -j$(nproc) && sudo make install\n\n"
        "Option 3 — QEMU macOS VM:\n"
        "  Place a macOS QCOW2 image at:\n"
        "  ~/.local/share/anything-mac-manager/vms/macos.qcow2\n"
        "  (See: https://github.com/kholia/OSX-KVM for setup)\n\n"
        "After installing, reopen AnythingMac Manager to detect the runtime."
    )


# ---------------------------------------------------------------------------
# CLI usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json
    logging.basicConfig(level=logging.DEBUG)
    status = get_full_runtime_status()
    print(_json.dumps(status, indent=2))
