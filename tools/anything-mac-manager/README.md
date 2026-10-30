# Darling App Manager

A modern GTK4 + Libadwaita GUI application (inspired by Gear Lever and GDebi) for inspecting, installing, and managing macOS applications inside **Darling** on Ubuntu.

![Darling App Manager](io.github.anythingmac.Manager.svg)

---

## Key Features

1. **GDebi / Gear Lever Style Installer (Page 1)**:
   - **Drag and Drop**: Drop `.dmg`, `.pkg`, or `.app` bundles straight into the window.
   - **File Choosers**: Native GTK file and folder dialogs with format filters.
   - **Live Metadata**:
     - CFBundleName, Display Name, Bundle Identifier, Version, Build Number
     - Mach-O binary architecture inspection: `x86_64`, `Universal 2 (x86_64 + arm64)`, `arm64 (Apple Silicon)`, `i386`
     - Minimum macOS version with marketing name lookup (e.g. `macOS 10.14 (Mojave)`)
     - Executable binary name and bundle size on disk
   - **Visual Feedback**:
     - Modern architecture badges (green for Darling-compatible x86_64/Universal 2, warning for arm64-only).
     - Asynchronous non-blocking inspection and progress reporting with animated spinners and progress bars.
   - **One-Click Installation**: Copies the `.app` bundle into Darling prefix (`~/.darling/Applications/`), installs icons, and registers GNOME Dash launchers.

2. **Application Library (Page 2)**:
   - Lists all macOS applications installed in your Darling prefix.
   - Real-time search filter for instant lookup.
   - **Launch Button**: Runs apps directly via `darling launch`.
   - **Reveal in Files**: Opens the containing folder in GNOME Files (Nautilus).
   - **Uninstall Button**: Prompts with Libadwaita `Adw.AlertDialog` confirmation, then cleanly removes the `.app` bundle, `.desktop` launcher, and system icons.

3. **Prefix & Runtime Status (Page 3)**:
   - Darling executable detection (`which darling`, version check).
   - Prefix path (`~/.darling`) and disk space consumption.
   - Kernel module / `/dev/mach` check.
   - Host CPU architecture translation status.
   - Quick actions: "Open Prefix in Files", "Launch Darling Terminal", "Initialize / Repair Prefix", and "Clear Temp Cache".

4. **Robust Format Support**:
   - **`.app` Bundles**: Inspects binary plists, XML plists, and Mach-O headers.
   - **`.icns` Icons**: Pillow-powered multi-resolution extraction (512x512, 256x256, 128x128, 64x64, 32x32) with elegant fallback squircle generator.
   - **`.dmg` Apple Disk Images**: Supports Darling native `hdiutil attach`, 7-Zip (`7z`), `dmg2img`, and pure-Python Apple UDIF chunk decompressor.
   - **`.pkg` Installer Packages**: Modern XAR archive unpacker with pure-Python TOC decompression and `/usr/bin/cpio` payload extraction.

---

## Directory Structure

```text
tools/anything-mac-manager/
├── anything_mac_backend.py                  # Core inspection, Mach-O parser, icon extractor & prefix manager
├── anything_mac_runtime.py                  # Runtime detection and bwrap launch path
├── darling                            # User-local Darling CLI runner
├── librootless.c                      # Source for the preload shim built by install.sh
├── anything-mac-manager.py                  # Modern GTK4 + Libadwaita GUI application
├── io.github.anythingmac.Manager.desktop # FreeDesktop application desktop entry
├── io.github.anythingmac.Manager.svg     # Scalable vector application icon
├── install.sh                          # Installation script for ~/.local
├── test_backend.py                     # Unit and integration test suite
└── README.md                           # Documentation
```

---

## Requirements

- **Operating System**: Ubuntu 24.04 / 26.04 LTS (or any modern Linux distribution with GTK4)
- **Python**: 3.10+
- **Python Packages**:
  - `PyGObject` (Gtk 4.0, Adw 1.0)
  - `Pillow` (PIL)
- **System Tools** (standard on Ubuntu):
  - `cpio`
  - `update-desktop-database`
  - `gtk-update-icon-cache`
- **Optional**:
  - `darling` (to execute macOS binaries)
  - `p7zip-full` / `7zz` (for compressed DMG images)

---

## Installation

Run the provided installation script:

```bash
chmod +x tools/anything-mac-manager/install.sh
./tools/anything-mac-manager/install.sh
```

This installs:
- Executable script: `~/.local/bin/anything-mac-manager`
- CLI forwarder: `~/.local/bin/darling` (prefers `~/.local/darling/usr/bin/darling`, then a system Darling binary)
- Application code & assets: `~/.local/share/anything-mac-manager/`
- Desktop shortcut: `~/.local/share/applications/io.github.anythingmac.Manager.desktop`
- Scalable and raster icons: `~/.local/share/icons/hicolor/*/apps/`

The CLI forwarder translates `darling launch /Applications/Name.app` into
Darling's `shell open` command and runs the managed runtime in Bubblewrap. The
installer builds `librootless.so` from the included source when a managed runtime
is present. Runtime status stays unverified until executable-path RPC and host
display forwarding succeed; file presence alone does not indicate a working GUI
runtime.

---

## Running the Application

### From GNOME Shell:
Search for **"Darling App Manager"** in the GNOME App Grid or Dash and press Enter.

### From Terminal:
```bash
anything-mac-manager
```

### Inspecting / Installing a specific package directly:
```bash
anything-mac-manager /path/to/Application.dmg
# or
anything-mac-manager /path/to/Application.app
```

---

## Running Tests

Run the backend unit test suite:

```bash
python3 tools/anything-mac-manager/test_backend.py
```
