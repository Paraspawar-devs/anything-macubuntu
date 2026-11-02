#!/usr/bin/env bash
set -e

# AnythingMac Manager Installer for Ubuntu / FreeDesktop
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PREFIX="${HOME}/.local"
BIN_DIR="${PREFIX}/bin"
APP_DATA_DIR="${PREFIX}/share/anything-mac-manager"
DESKTOP_DIR="${PREFIX}/share/applications"
ICON_DIR="${PREFIX}/share/icons/hicolor/scalable/apps"

echo "=============================================="
echo " Installing AnythingMac Manager for Linux"
echo "=============================================="

# 1. Create target directories
mkdir -p "${BIN_DIR}"
mkdir -p "${APP_DATA_DIR}"
mkdir -p "${DESKTOP_DIR}"
mkdir -p "${ICON_DIR}"

# Remove legacy Darling desktop entries, icons, and symlinks
rm -f "${DESKTOP_DIR}/org.darlinghq.DarlingManager.desktop"
rm -f "${DESKTOP_DIR}/org.darlinghq."*.desktop
rm -f "${DESKTOP_DIR}/darling-"*.desktop
rm -f "${BIN_DIR}/darling" "${BIN_DIR}/darling-manager"

# 2. Copy application files
echo "-> Installing application files to ${APP_DATA_DIR}..."
cp -f "${SCRIPT_DIR}/anything_mac_backend.py" "${APP_DATA_DIR}/"
cp -f "${SCRIPT_DIR}/anything_mac_runtime.py" "${APP_DATA_DIR}/"
cp -f "${SCRIPT_DIR}/generate_tahoe_shim.py" "${APP_DATA_DIR}/"
cp -f "${SCRIPT_DIR}/anything-mac" "${BIN_DIR}/anything-mac"
chmod +x "${BIN_DIR}/anything-mac"
ln -sfn "${BIN_DIR}/anything-mac" "${BIN_DIR}/amac"

# Build the user-local interception shim when a managed runtime exists.
if [[ -d "${PREFIX}/anything-mac/usr/bin" || -d "${PREFIX}/darling/usr/bin" ]]; then
    target_dir="${PREFIX}/anything-mac"
    [[ -d "$target_dir" ]] || target_dir="${PREFIX}/darling"
    if command -v gcc >/dev/null 2>&1; then
        echo "-> Building rootless runtime shim..."
        gcc -shared -fPIC -O2 \
            -o "${target_dir}/librootless.so" "${SCRIPT_DIR}/librootless.c" -ldl
    fi
fi
cp -f "${SCRIPT_DIR}/anything-mac-manager.py" "${APP_DATA_DIR}/"
cp -f "${SCRIPT_DIR}/io.github.anythingmac.Manager.svg" "${APP_DATA_DIR}/"
chmod +x "${APP_DATA_DIR}/anything-mac-manager.py"

# 3. Create launcher in ~/.local/bin
echo "-> Creating launcher script at ${BIN_DIR}/anything-mac-manager..."
cat << 'EOF' > "${BIN_DIR}/anything-mac-manager"
#!/usr/bin/env bash
exec python3 "${HOME}/.local/share/anything-mac-manager/anything-mac-manager.py" "$@"
EOF
chmod +x "${BIN_DIR}/anything-mac-manager"
ln -sfn "${BIN_DIR}/anything-mac-manager" "${BIN_DIR}/amac-manager"

# 4. Install desktop entry
echo "-> Installing GNOME desktop entry to ${DESKTOP_DIR}..."
cp -f "${SCRIPT_DIR}/io.github.anythingmac.Manager.desktop" "${DESKTOP_DIR}/"
chmod +x "${DESKTOP_DIR}/io.github.anythingmac.Manager.desktop"

# 5. Install vector icon
echo "-> Installing scalable icon to ${ICON_DIR}..."
cp -f "${SCRIPT_DIR}/io.github.anythingmac.Manager.svg" "${ICON_DIR}/"

# 6. Generate rasterized PNG icons at standard resolutions
echo "-> Generating PNG icon resolutions for desktop launchers..."
python3 - << 'PYEOF'
import os
import pathlib

try:
    import gi
    gi.require_version('Rsvg', '2.0')
    from gi.repository import Rsvg, GdkPixbuf

    svg_path = os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps/io.github.anythingmac.Manager.svg")
    hicolor = os.path.expanduser("~/.local/share/icons/hicolor")
    handle = Rsvg.Handle.new_from_file(svg_path)
    pixbuf = handle.get_pixbuf()

    for size in [512, 256, 128, 64, 48, 32]:
        dest_dir = os.path.join(hicolor, f"{size}x{size}", "apps")
        os.makedirs(dest_dir, exist_ok=True)
        dest_png = os.path.join(dest_dir, "io.github.anythingmac.Manager.png")
        if pixbuf:
            scaled = pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
            scaled.savev(dest_png, "png", [], [])
except Exception as e:
    pass
PYEOF

# 7. Update desktop database & icon cache
echo "-> Updating desktop database and icon caches..."
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${DESKTOP_DIR}" || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f "${PREFIX}/share/icons/hicolor" || true
fi

echo "=============================================="
echo " Installation Complete!"
echo " AnythingMac Manager is ready to use."
echo ""
echo " You can launch it by:"
echo "   1. Running 'anything-mac-manager' (or 'amac-manager') from terminal"
echo "   2. Searching for 'AnythingMac Manager' in the GNOME Dash"
echo "=============================================="
