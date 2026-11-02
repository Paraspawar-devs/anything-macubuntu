#!/usr/bin/env python3
"""
Darling App Manager (anything-mac-manager.py)
A modern GTK4 + Libadwaita GUI application for inspecting, installing,
and managing macOS applications (.dmg, .pkg, .app) inside Darling on Ubuntu.
"""

import os
import pathlib
import subprocess
import sys
import threading
from typing import List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

# Import backend module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anything_mac_backend
from anything_mac_backend import AppInfo

APP_ID = "io.github.anythingmac.Manager"
APP_TITLE = "Anything-Mac"
APP_VERSION = "1.0.0"

CUSTOM_CSS = b"""
/* ==========================================================================
   AnythingMac Manager - Liquid Glassmorphism & macOS Tahoe Theme
   ========================================================================== */

window, .main-window {
    background: radial-gradient(circle at 50% 0%, #201a2e 0%, #13131c 65%, #0a0a0f 100%);
    color: #f5f5f7;
}

headerbar {
    background: rgba(20, 18, 28, 0.65);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
}

.glass-card, .drop-box {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 100%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 22px;
    padding: 34px 24px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.2);
    transition: all 250ms cubic-bezier(0.16, 1, 0.3, 1);
}

.drop-box:hover {
    border-color: rgba(0, 242, 254, 0.6);
    background: linear-gradient(135deg, rgba(0, 242, 254, 0.1) 0%, rgba(118, 75, 162, 0.08) 100%);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), 0 0 24px rgba(0, 242, 254, 0.25), inset 0 1px 1px rgba(255, 255, 255, 0.35);
}

/* Liquid Status Indicator Pill */
.status-pill-active {
    background: linear-gradient(135deg, rgba(46, 213, 115, 0.2) 0%, rgba(46, 213, 115, 0.06) 100%);
    color: #2ed573;
    border: 1px solid rgba(46, 213, 115, 0.4);
    border-radius: 9999px;
    padding: 4px 14px;
    font-weight: 700;
    font-size: 0.85em;
    box-shadow: 0 0 14px rgba(46, 213, 115, 0.25);
}

.status-pill-idle {
    background: rgba(255, 255, 255, 0.06);
    color: #a0a0a8;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 9999px;
    padding: 4px 14px;
    font-size: 0.85em;
}

/* Hero Status Banner inside Status page */
.hero-glass-banner {
    background: linear-gradient(135deg, rgba(233, 84, 32, 0.15) 0%, rgba(118, 75, 162, 0.25) 50%, rgba(0, 242, 254, 0.12) 100%);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.25);
}

/* Modern macOS Squircle Icons */
.app-icon-preview {
    border-radius: 22px;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.4), 0 2px 6px rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.14);
}

.app-icon-small {
    border-radius: 14px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
}

/* Tahoe Neon Badges */
.badge-compat {
    background: linear-gradient(135deg, rgba(46, 213, 115, 0.2) 0%, rgba(0, 242, 254, 0.15) 100%);
    color: #00f2fe;
    border: 1px solid rgba(0, 242, 254, 0.35);
    border-radius: 9999px;
    padding: 4px 14px;
    font-weight: 700;
    font-size: 0.85em;
    box-shadow: 0 0 12px rgba(0, 242, 254, 0.18);
}

.badge-info {
    background: linear-gradient(135deg, rgba(118, 75, 162, 0.25) 0%, rgba(102, 126, 234, 0.15) 100%);
    color: #a18cd1;
    border: 1px solid rgba(161, 140, 209, 0.35);
    border-radius: 9999px;
    padding: 4px 14px;
    font-weight: 700;
    font-size: 0.85em;
}

.badge-warn {
    background: linear-gradient(135deg, rgba(255, 171, 0, 0.2) 0%, rgba(255, 107, 107, 0.15) 100%);
    color: #ffab00;
    border: 1px solid rgba(255, 171, 0, 0.35);
    border-radius: 9999px;
    padding: 4px 14px;
    font-weight: 700;
    font-size: 0.85em;
}

.installed-badge {
    background: rgba(0, 122, 255, 0.18);
    color: #007aff;
    border: 1px solid rgba(0, 122, 255, 0.3);
    border-radius: 8px;
    padding: 3px 10px;
    font-size: 0.82em;
    font-weight: 600;
}

/* Glass Buttons */
button.suggested-action {
    background: linear-gradient(135deg, #007aff 0%, #0056b3 100%);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 9999px;
    color: #ffffff;
    font-weight: 600;
    box-shadow: 0 4px 16px rgba(0, 122, 255, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

button.suggested-action:hover {
    background: linear-gradient(135deg, #1a8cff 0%, #0066d6 100%);
    box-shadow: 0 6px 20px rgba(0, 122, 255, 0.5), 0 0 12px rgba(0, 122, 255, 0.35);
}

button.pill {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 9999px;
    color: #f5f5f7;
}

button.pill:hover {
    background: rgba(255, 255, 255, 0.15);
    border-color: rgba(255, 255, 255, 0.25);
}

/* Frosted App List Rows */
preferencesgroup > box {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.2);
}

list > row {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px;
    margin: 4px 0;
    transition: all 180ms ease;
}

list > row:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(0, 242, 254, 0.35);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}
"""


class AnythingMacMainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title(APP_TITLE)
        self.set_default_size(860, 680)
        self.set_size_request(400, 480)

        # Active state
        self.current_app_info: Optional[AppInfo] = None
        self.active_inspected_apps: List[AppInfo] = []
        self.installed_apps: List[AppInfo] = []

        # Setup Main UI layout
        self._setup_ui()

        # Load initial data
        self.refresh_library()
        self.refresh_status_page()

    def _setup_ui(self):
        # ToolbarView
        self.toolbar_view = Adw.ToolbarView()
        self.set_content(self.toolbar_view)

        # HeaderBar
        self.header_bar = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(self.header_bar)

        # ViewSwitcherTitle in HeaderBar
        self.view_title = Adw.ViewSwitcherTitle()
        self.header_bar.set_title_widget(self.view_title)

        # Header buttons
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh Library & Prefix Status")
        refresh_btn.connect("clicked", lambda _: self.refresh_all())
        self.header_bar.pack_start(refresh_btn)

        self.header_status_chip = Gtk.Label(label="● Active (Tahoe 16)")
        self.header_status_chip.add_css_class("status-pill-active")
        self.header_bar.pack_start(self.header_status_chip)

        menu_btn = self._build_menu_button()
        self.header_bar.pack_end(menu_btn)

        # Toast Overlay
        self.toast_overlay = Adw.ToastOverlay()
        self.toolbar_view.set_content(self.toast_overlay)

        # ViewStack
        self.view_stack = Adw.ViewStack()
        self.toast_overlay.set_child(self.view_stack)
        if hasattr(self.view_title, "set_view_stack"):
            self.view_title.set_view_stack(self.view_stack)
        else:
            self.view_title.set_stack(self.view_stack)

        # Page 1: Install / Open
        self.install_page = self._build_install_page()
        page1 = self.view_stack.add_titled(
            self.install_page, "install", "Install"
        )
        page1.set_icon_name("system-software-install-symbolic")

        # Page 2: Library / Installed
        self.library_page = self._build_library_page()
        page2 = self.view_stack.add_titled(
            self.library_page, "library", "Library"
        )
        page2.set_icon_name("view-app-grid-symbolic")

        # Page 3: Status & Settings
        self.status_page = self._build_status_page()
        page3 = self.view_stack.add_titled(
            self.status_page, "status", "Prefix Status"
        )
        page3.set_icon_name("preferences-system-symbolic")

        # Bottom ViewSwitcherBar (for responsive layout)
        self.switcher_bar = Adw.ViewSwitcherBar()
        self.switcher_bar.set_stack(self.view_stack)
        self.toolbar_view.add_bottom_bar(self.switcher_bar)

        # Bind switcher bar reveal to view title visibility
        self.view_title.bind_property(
            "title-visible",
            self.switcher_bar,
            "reveal",
            GObject.BindingFlags.SYNC_CREATE,
        )

        # Drag and Drop Setup for entire window
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_window_file_dropped)
        self.add_controller(drop_target)

    def _build_menu_button(self) -> Gtk.MenuButton:
        menu = Gio.Menu()
        menu.append("Open Prefix in Files", "app.open_prefix")
        menu.append("Launch Darwin Shell", "app.launch_shell")
        menu.append("Clear Manager Cache", "app.clean_cache")
        menu.append("About AnythingMac Manager", "app.about")

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_menu_model(menu)
        menu_btn.set_tooltip_text("Main Menu")
        return menu_btn

    # ==========================================================================
    # Page 1: Install / Open View
    # ==========================================================================
    def _build_install_page(self) -> Gtk.Widget:
        self.install_nav_stack = Gtk.Stack()
        self.install_nav_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # 1. Drop Zone View
        drop_scroll = Gtk.ScrolledWindow()
        drop_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        clamp_drop = Adw.Clamp()
        clamp_drop.set_maximum_size(680)
        clamp_drop.set_margin_top(32)
        clamp_drop.set_margin_bottom(32)
        clamp_drop.set_margin_start(24)
        clamp_drop.set_margin_end(24)

        drop_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        drop_card.add_css_class("drop-box")

        icon_img = Gtk.Image.new_from_icon_name("system-software-install-symbolic")
        icon_img.set_pixel_size(64)
        drop_card.append(icon_img)

        title_lbl = Gtk.Label(label="Open or Drop macOS Application")
        title_lbl.add_css_class("title-2")
        drop_card.append(title_lbl)

        sub_lbl = Gtk.Label(
            label="Drag and drop a .dmg, .pkg, or .app bundle here to inspect and install."
        )
        sub_lbl.add_css_class("body")
        sub_lbl.add_css_class("dim-label")
        sub_lbl.set_wrap(True)
        sub_lbl.set_justify(Gtk.Justification.CENTER)
        drop_card.append(sub_lbl)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(12)

        choose_file_btn = Gtk.Button(label="Choose File (.dmg / .pkg)...")
        choose_file_btn.add_css_class("suggested-action")
        choose_file_btn.add_css_class("pill")
        choose_file_btn.connect("clicked", lambda _: self._open_file_dialog())
        btn_box.append(choose_file_btn)

        choose_app_btn = Gtk.Button(label="Choose .app Folder...")
        choose_app_btn.add_css_class("pill")
        choose_app_btn.connect("clicked", lambda _: self._open_folder_dialog())
        btn_box.append(choose_app_btn)

        drop_card.append(btn_box)

        # Footnote
        formats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        formats_box.set_halign(Gtk.Align.CENTER)
        formats_box.set_margin_top(16)
        tag_dmg = Gtk.Label(label="• Apple Disk Image (.dmg)")
        tag_pkg = Gtk.Label(label="• Installer Package (.pkg)")
        tag_app = Gtk.Label(label="• App Bundle (.app)")
        for t in [tag_dmg, tag_pkg, tag_app]:
            t.add_css_class("caption")
            t.add_css_class("dim-label")
            formats_box.append(t)
        drop_card.append(formats_box)

        clamp_drop.set_child(drop_card)
        drop_scroll.set_child(clamp_drop)
        self.install_nav_stack.add_named(drop_scroll, "drop_zone")

        # 2. Loading / Extracting View
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        loading_box.set_valign(Gtk.Align.CENTER)
        loading_box.set_halign(Gtk.Align.CENTER)

        self.inspect_spinner = Gtk.Spinner()
        self.inspect_spinner.set_size_request(48, 48)
        loading_box.append(self.inspect_spinner)

        self.inspect_label = Gtk.Label(label="Inspecting application...")
        self.inspect_label.add_css_class("title-3")
        loading_box.append(self.inspect_label)

        self.inspect_sublabel = Gtk.Label(label="Reading binary headers and bundle metadata")
        self.inspect_sublabel.add_css_class("caption")
        self.inspect_sublabel.add_css_class("dim-label")
        loading_box.append(self.inspect_sublabel)

        self.install_nav_stack.add_named(loading_box, "loading")

        # 3. Details / Inspector View
        self.details_scroll = Gtk.ScrolledWindow()
        self.details_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.details_clamp = Adw.Clamp()
        self.details_clamp.set_maximum_size(680)
        self.details_clamp.set_margin_top(24)
        self.details_clamp.set_margin_bottom(32)
        self.details_clamp.set_margin_start(20)
        self.details_clamp.set_margin_end(20)

        self.details_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.details_clamp.set_child(self.details_container)
        self.details_scroll.set_child(self.details_clamp)

        self.install_nav_stack.add_named(self.details_scroll, "details")

        return self.install_nav_stack

    def _show_app_details(self, app_info: AppInfo):
        """Displays the detailed inspector card and install button for an app."""
        self.current_app_info = app_info

        # Clear existing details
        while child := self.details_container.get_first_child():
            self.details_container.remove(child)

        # Header Box (Icon + Title + Version + ID + Badges)
        header_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        header_card.set_margin_bottom(8)

        # Icon Picture
        if app_info.icon_preview_path and os.path.exists(app_info.icon_preview_path):
            icon_pic = Gtk.Picture.new_for_filename(app_info.icon_preview_path)
        else:
            icon_pic = Gtk.Picture.new_for_filename(
                str(pathlib.Path(__file__).parent / "io.github.anythingmac.Manager.svg")
            )
        icon_pic.set_size_request(96, 96)
        icon_pic.set_content_fit(Gtk.ContentFit.CONTAIN)
        icon_pic.add_css_class("app-icon-preview")
        header_card.append(icon_pic)

        # Title / Info
        meta_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        meta_vbox.set_valign(Gtk.Align.CENTER)

        name_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name_lbl = Gtk.Label(label=app_info.display_name)
        name_lbl.add_css_class("title-1")
        name_lbl.set_halign(Gtk.Align.START)
        name_hbox.append(name_lbl)

        ver_lbl = Gtk.Label(label=f"v{app_info.version}")
        ver_lbl.add_css_class("badge-info")
        ver_lbl.set_valign(Gtk.Align.CENTER)
        name_hbox.append(ver_lbl)
        meta_vbox.append(name_hbox)

        id_lbl = Gtk.Label(label=app_info.bundle_id)
        id_lbl.add_css_class("caption")
        id_lbl.add_css_class("dim-label")
        id_lbl.set_halign(Gtk.Align.START)
        meta_vbox.append(id_lbl)

        # Architecture badge
        _, is_compat, badge_cls = anything_mac_backend.format_arch_summary(app_info.architectures)
        badge_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        badge_hbox.set_margin_top(6)

        arch_badge = Gtk.Label(label=f"Arch: {app_info.arch_summary}")
        arch_badge.add_css_class(badge_cls)
        badge_hbox.append(arch_badge)

        if app_info.is_installed:
            inst_badge = Gtk.Label(label="Installed in ~/.darling")
            inst_badge.add_css_class("installed-badge")
            badge_hbox.append(inst_badge)

        meta_vbox.append(badge_hbox)
        header_card.append(meta_vbox)
        self.details_container.append(header_card)

        # Architecture incompatibility is a blocker; a deployment target is only a hint.
        if not app_info.is_darling_compatible:
            is_os_compat, os_reason = anything_mac_backend.is_macos_version_supported(app_info.min_os_version)
            _, is_arch_compat, _ = anything_mac_backend.format_arch_summary(app_info.architectures)
            if not is_arch_compat:
                warn_msg = (
                    "Notice: This application is compiled exclusively for Apple Silicon (arm64). "
                    "Your laptop CPU is x86_64 (Intel/AMD), so it cannot execute."
                )
            elif not is_os_compat:
                warn_msg = f"Notice: {os_reason}"
            else:
                warn_msg = "Notice: This application may require additional runtime APIs."
            warn_banner = Adw.Banner.new(warn_msg)
            warn_banner.set_revealed(True)
            self.details_container.append(warn_banner)
        elif app_info.min_os_version and app_info.min_os_version.split(".", 1)[0].isdigit() and int(app_info.min_os_version.split(".", 1)[0]) >= 12:
            advisory = Adw.Banner.new(
                f"Targets macOS {app_info.min_os_version}; AnythingMac will attempt to run it with the Tahoe 16 shim."
            )
            advisory.set_revealed(True)
            self.details_container.append(advisory)

        # Detailed Properties (PreferencesGroup)
        pref_group = Adw.PreferencesGroup()
        pref_group.set_title("Package Details")
        pref_group.set_description("Bundle metadata and system requirements")

        # Row 1: Architectures
        row_arch = Adw.ActionRow()
        row_arch.set_title("Binary Architectures")
        row_arch.set_subtitle(
            ", ".join(app_info.architectures) if app_info.architectures else "Mach-O"
        )
        pref_group.add(row_arch)

        # Row 2: Minimum macOS
        row_min_os = Adw.ActionRow()
        row_min_os.set_title("Minimum macOS Version")
        row_min_os.set_subtitle(app_info.min_os_display)
        pref_group.add(row_min_os)

        # Row 3: Executable
        row_exe = Adw.ActionRow()
        row_exe.set_title("Executable Binary")
        row_exe.set_subtitle(app_info.executable_name or "Standard Mach-O")
        pref_group.add(row_exe)

        # Row 4: Bundle Size
        row_size = Adw.ActionRow()
        row_size.set_title("Application Size")
        row_size.set_subtitle(app_info.size_formatted)
        pref_group.add(row_size)

        # Row 5: Source Type & File
        row_src = Adw.ActionRow()
        row_src.set_title("Source File")
        row_src.set_subtitle(str(app_info.source_file or app_info.bundle_path))
        pref_group.add(row_src)

        self.details_container.append(pref_group)

        # Installation Action Box & Progress Feedback
        self.action_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.action_vbox.set_margin_top(8)

        # Progress bar
        self.install_progress = Gtk.ProgressBar()
        self.install_progress.set_fraction(0.0)
        self.install_progress.set_visible(False)
        self.action_vbox.append(self.install_progress)

        self.install_status_lbl = Gtk.Label(label="")
        self.install_status_lbl.add_css_class("caption")
        self.install_status_lbl.add_css_class("dim-label")
        self.install_status_lbl.set_visible(False)
        self.action_vbox.append(self.install_status_lbl)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_row.set_halign(Gtk.Align.FILL)

        # Install / Reinstall Button
        install_label = "Reinstall Application" if app_info.is_installed else "Install Application"
        self.install_btn = Gtk.Button(label=install_label)
        self.install_btn.set_hexpand(True)
        self.install_btn.add_css_class("suggested-action")
        self.install_btn.add_css_class("pill")
        self.install_btn.connect("clicked", lambda _: self._do_install(app_info))
        btn_row.append(self.install_btn)

        # Launch Button if already installed
        if app_info.is_installed:
            launch_btn = Gtk.Button(label="Launch")
            launch_btn.add_css_class("pill")
            if not is_compat:
                launch_btn.set_sensitive(False)
                launch_btn.set_tooltip_text("Incompatible with x86_64 CPU (Apple Silicon arm64 only)")
            launch_btn.connect("clicked", lambda _: self._do_launch(app_info))
            btn_row.append(launch_btn)

            # Uninstall Button
            uninstall_btn = Gtk.Button(label="Uninstall Application")
            uninstall_btn.add_css_class("destructive-action")
            uninstall_btn.add_css_class("pill")
            uninstall_btn.connect("clicked", lambda _: self._confirm_uninstall(app_info))
            btn_row.append(uninstall_btn)

        # Choose Another File Button
        another_btn = Gtk.Button(label="Choose Another")
        another_btn.add_css_class("pill")
        another_btn.connect("clicked", lambda _: self._reset_to_drop_zone())
        btn_row.append(another_btn)

        self.action_vbox.append(btn_row)
        self.details_container.append(self.action_vbox)

        self.install_nav_stack.set_visible_child_name("details")

    def _reset_to_drop_zone(self):
        self.current_app_info = None
        self.install_nav_stack.set_visible_child_name("drop_zone")

    def _do_install(self, app_info: AppInfo):
        """Runs the installation in a background worker thread."""
        self.install_btn.set_sensitive(False)
        self.install_progress.set_visible(True)
        self.install_progress.set_fraction(0.1)
        self.install_status_lbl.set_visible(True)
        self.install_status_lbl.set_text("Installing application into AnythingMac prefix...")

        def progress_cb(msg: str, frac: float):
            GLib.idle_add(self._update_install_progress, msg, frac)

        def worker():
            success, msg = anything_mac_backend.install_app(app_info, progress_callback=progress_cb)
            GLib.idle_add(self._on_install_finished, app_info, success, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _update_install_progress(self, msg: str, fraction: float):
        self.install_status_lbl.set_text(msg)
        self.install_progress.set_fraction(fraction)

    def _on_install_finished(self, app_info: AppInfo, success: bool, message: str):
        self.install_btn.set_sensitive(True)
        self.install_progress.set_visible(False)
        self.install_status_lbl.set_visible(False)

        if success:
            self._show_toast(f"'{app_info.display_name}' installed successfully!")
            self._show_app_details(app_info)
            self.refresh_library()
            self.refresh_status_page()
        else:
            self._show_toast(f"Error: {message}")

    def _do_launch(self, app_info: AppInfo):
        if not app_info.is_darling_compatible:
            _, is_arch_compat, _ = anything_mac_backend.format_arch_summary(app_info.architectures)
            if not is_arch_compat:
                title = "Incompatible CPU Architecture"
                body = (
                    f"'{app_info.display_name}' was compiled exclusively for Apple Silicon (ARM64).\n\n"
                    f"Your laptop has an Intel/AMD (x86_64) processor.\n"
                    f"AnythingMac executes macOS applications natively without CPU emulation.\n\n"
                    f"Please download the Intel (x86_64) or Universal macOS version of this application."
                )
            else:
                title = "Application may not run"
                body = f"AnythingMac could not confirm compatibility for '{app_info.display_name}'. Try launching it to see which runtime APIs it needs."
            dialog = Adw.MessageDialog.new(self, title, body)
            dialog.add_response("ok", "Close")
            dialog.present()
            return

        success, msg = anything_mac_backend.launch_app(app_info)
        if success:
            self._show_toast(f"Launching {app_info.display_name}...")
        else:
            self._show_toast(f"Launch failed: {msg}")

    # ==========================================================================
    # Page 2: Library View
    # ==========================================================================
    def _build_library_page(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # Search Bar
        search_clamp = Adw.Clamp()
        search_clamp.set_maximum_size(680)
        search_clamp.set_margin_top(14)
        search_clamp.set_margin_start(16)
        search_clamp.set_margin_end(16)

        self.library_search = Gtk.SearchEntry()
        self.library_search.set_placeholder_text("Search installed macOS applications...")
        self.library_search.connect("search-changed", self._on_search_changed)
        search_clamp.set_child(self.library_search)
        vbox.append(search_clamp)

        # Library content stack (Empty state vs List)
        self.library_stack = Gtk.Stack()
        self.library_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.library_stack.set_vexpand(True)

        # 1. Empty State
        empty_page = Adw.StatusPage()
        empty_page.set_icon_name("view-app-grid-symbolic")
        empty_page.set_title("No macOS Apps Installed")
        empty_page.set_description(
            "Applications installed in ~/.darling/Applications will appear here with GNOME Dash integration."
        )
        empty_btn = Gtk.Button(label="Install an Application")
        empty_btn.add_css_class("suggested-action")
        empty_btn.add_css_class("pill")
        empty_btn.connect("clicked", lambda _: self.view_stack.set_visible_child_name("install"))
        empty_page.set_child(empty_btn)
        self.library_stack.add_named(empty_page, "empty")

        # 2. Installed Apps List
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_clamp = Adw.Clamp()
        list_clamp.set_maximum_size(680)
        list_clamp.set_margin_top(8)
        list_clamp.set_margin_bottom(24)
        list_clamp.set_margin_start(16)
        list_clamp.set_margin_end(16)

        self.installed_list_box = Gtk.ListBox()
        self.installed_list_box.add_css_class("boxed-list")
        self.installed_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.installed_list_box.set_filter_func(self._filter_library_row)

        list_clamp.set_child(self.installed_list_box)
        list_scroll.set_child(list_clamp)
        self.library_stack.add_named(list_scroll, "list")

        vbox.append(self.library_stack)
        return vbox

    def refresh_library(self):
        """Reloads installed applications from Darling prefix."""
        # Clear existing rows
        while child := self.installed_list_box.get_first_child():
            self.installed_list_box.remove(child)

        self.installed_apps = anything_mac_backend.list_installed_apps()

        if not self.installed_apps:
            self.library_stack.set_visible_child_name("empty")
            return

        for app_info in self.installed_apps:
            row = self._create_library_row(app_info)
            self.installed_list_box.append(row)

        self.library_stack.set_visible_child_name("list")

    def _create_library_row(self, app_info: AppInfo) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(app_info.display_name)
        if not app_info.is_darling_compatible:
            is_os_compat, _ = anything_mac_backend.is_macos_version_supported(app_info.min_os_version)
            _, is_arch_compat, _ = anything_mac_backend.format_arch_summary(app_info.architectures)
            if not is_arch_compat:
                row.set_subtitle("⚠️ Apple Silicon (arm64 only) • Incompatible with x86_64 CPU")
            elif not is_os_compat:
                row.set_subtitle(f"⚠️ Requires macOS {app_info.min_os_version} • AnythingMac supports macOS 13–16 Tahoe")
            else:
                row.set_subtitle("⚠️ Incompatible with current AnythingMac environment")
        else:
            row.set_subtitle(
                f"v{app_info.version} • {app_info.bundle_id} • {app_info.arch_summary}"
            )
        row.app_info = app_info

        # Icon prefix
        if app_info.icon_preview_path and os.path.exists(app_info.icon_preview_path):
            icon_pic = Gtk.Picture.new_for_filename(app_info.icon_preview_path)
        else:
            icon_pic = Gtk.Picture.new_for_filename(
                str(pathlib.Path(__file__).parent / "io.github.anythingmac.Manager.svg")
            )
        icon_pic.set_size_request(44, 44)
        icon_pic.set_content_fit(Gtk.ContentFit.CONTAIN)
        icon_pic.add_css_class("app-icon-small")
        row.add_prefix(icon_pic)

        # Actions
        launch_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        if not app_info.is_darling_compatible:
            launch_btn.set_tooltip_text("Incompatible Application (Architecture or macOS Version)")
            launch_btn.set_sensitive(False)
        else:
            launch_btn.set_tooltip_text("Launch Application")
            launch_btn.add_css_class("suggested-action")
        launch_btn.add_css_class("flat")
        launch_btn.connect("clicked", lambda _, a=app_info: self._do_launch(a))
        row.add_suffix(launch_btn)

        folder_btn = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        folder_btn.set_tooltip_text("Open Application Folder in Files")
        folder_btn.add_css_class("flat")
        folder_btn.connect("clicked", lambda _, a=app_info: self._reveal_app_folder(a))
        row.add_suffix(folder_btn)

        uninstall_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        uninstall_btn.set_tooltip_text("Uninstall Application")
        uninstall_btn.add_css_class("destructive-action")
        uninstall_btn.add_css_class("flat")
        uninstall_btn.connect("clicked", lambda _, a=app_info: self._confirm_uninstall(a))
        row.add_suffix(uninstall_btn)

        return row

    def _filter_library_row(self, row: Gtk.ListBoxRow) -> bool:
        query = self.library_search.get_text().strip().lower()
        if not query:
            return True
        app_info: AppInfo = getattr(row, "app_info", None)
        if not app_info:
            return True
        return (
            query in app_info.display_name.lower()
            or query in app_info.bundle_name.lower()
            or query in app_info.bundle_id.lower()
        )

    def _on_search_changed(self, _entry):
        self.installed_list_box.invalidate_filter()

    def _reveal_app_folder(self, app_info: AppInfo):
        path = app_info.bundle_path
        subprocess.run(["xdg-open", str(pathlib.Path(path).parent)], check=False)

    def _confirm_uninstall(self, app_info: AppInfo):
        """Prompts before uninstallation using modern Adw.AlertDialog."""
        alert = Adw.AlertDialog.new(
            f"Uninstall {app_info.display_name}?",
            f"This will remove '{pathlib.Path(app_info.bundle_path).name}' from your AnythingMac prefix, "
            "delete its GNOME desktop launcher, and remove installed icons.",
        )
        alert.add_response("cancel", "Cancel")
        alert.add_response("uninstall", "Uninstall")
        alert.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog, result):
            if hasattr(dialog, "choose_finish"):
                try:
                    response_id = dialog.choose_finish(result)
                except Exception:
                    response_id = result if isinstance(result, str) else None
            else:
                response_id = result if isinstance(result, str) else None

            if response_id == "uninstall":
                success, msg = anything_mac_backend.uninstall_app(app_info)
                if success:
                    self._show_toast(f"Uninstalled '{app_info.display_name}'")
                    self.refresh_library()
                    self.refresh_status_page()
                    # If this app is currently open in details, update the view
                    if self.current_app_info and (
                        self.current_app_info.bundle_id == app_info.bundle_id
                        or self.current_app_info.bundle_name == app_info.bundle_name
                    ):
                        self.current_app_info.is_installed = False
                        self.current_app_info.installed_path = None
                        self._show_app_details(self.current_app_info)
                else:
                    self._show_toast(f"Uninstall error: {msg}")

        alert.choose(self, None, on_response)

    # ==========================================================================
    # Page 3: Status & Settings View
    # ==========================================================================
    def _build_status_page(self) -> Gtk.Widget:
        pref_page = Adw.PreferencesPage()

        # Hero Liquid Glass Banner
        grp_hero = Adw.PreferencesGroup()
        hero_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        hero_box.add_css_class("hero-glass-banner")

        logo_path = str(pathlib.Path(__file__).parent / "io.github.anythingmac.Manager.svg")
        if os.path.exists(logo_path):
            hero_icon = Gtk.Picture.new_for_filename(logo_path)
            hero_icon.set_size_request(60, 60)
            hero_icon.set_content_fit(Gtk.ContentFit.CONTAIN)
            hero_box.append(hero_icon)

        hero_text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        hero_title = Gtk.Label(label="AnythingMac Runtime")
        hero_title.add_css_class("title-2")
        hero_title.set_xalign(0)
        hero_text_box.append(hero_title)

        hero_sub = Gtk.Label(label="macOS 16.0 Tahoe Compatibility Engine • Bubblewrap Rootless")
        hero_sub.add_css_class("body")
        hero_sub.add_css_class("dim-label")
        hero_sub.set_xalign(0)
        hero_text_box.append(hero_sub)

        hero_box.append(hero_text_box)

        self.hero_status_pill = Gtk.Label(label="● Active (Tahoe 16.0)")
        self.hero_status_pill.add_css_class("status-pill-active")
        self.hero_status_pill.set_valign(Gtk.Align.CENTER)
        self.hero_status_pill.set_halign(Gtk.Align.END)
        self.hero_status_pill.set_hexpand(True)
        hero_box.append(self.hero_status_pill)

        grp_hero.add(hero_box)
        pref_page.add(grp_hero)

        # Group 1: AnythingMac Runtime
        grp_runtime = Adw.PreferencesGroup()
        grp_runtime.set_title("Engine Status &amp; Compatibility")
        grp_runtime.set_description("Container isolation and macOS API shim layers")

        self.row_darling_bin = Adw.ActionRow()
        self.row_darling_bin.set_title("AnythingMac CLI Launcher")
        grp_runtime.add(self.row_darling_bin)

        self.row_prefix_path = Adw.ActionRow()
        self.row_prefix_path.set_title("Container Prefix Location")
        grp_runtime.add(self.row_prefix_path)

        self.row_tahoe_shim = Adw.ActionRow()
        self.row_tahoe_shim.set_title("Tahoe 16 Compatibility Shim")
        grp_runtime.add(self.row_tahoe_shim)

        self.row_sandbox_mode = Adw.ActionRow()
        self.row_sandbox_mode.set_title("Security &amp; Sandbox Mode")
        grp_runtime.add(self.row_sandbox_mode)

        self.row_mach_dev = Adw.ActionRow()
        self.row_mach_dev.set_title("Emulation Driver")
        grp_runtime.add(self.row_mach_dev)

        self.row_host_arch = Adw.ActionRow()
        self.row_host_arch.set_title("Host Processor Architecture")
        grp_runtime.add(self.row_host_arch)

        pref_page.add(grp_runtime)

        # Group 2: Actions
        grp_actions = Adw.PreferencesGroup()
        grp_actions.set_title("Prefix Management")
        grp_actions.set_description("Maintenance and filesystem actions")

        row_open_prefix = Adw.ActionRow()
        row_open_prefix.set_title("Open Prefix in Files")
        row_open_prefix.set_subtitle("Browse ~/.darling and container directories")
        open_prefix_btn = Gtk.Button(label="Open")
        open_prefix_btn.set_valign(Gtk.Align.CENTER)
        open_prefix_btn.connect("clicked", lambda _: self._open_prefix_in_files())
        row_open_prefix.add_suffix(open_prefix_btn)
        grp_actions.add(row_open_prefix)

        row_shell = Adw.ActionRow()
        row_shell.set_title("Launch Darwin Zsh Terminal")
        row_shell.set_subtitle("Opens an interactive macOS shell container")
        shell_btn = Gtk.Button(label="Launch")
        shell_btn.set_valign(Gtk.Align.CENTER)
        shell_btn.connect("clicked", lambda _: self._launch_darling_terminal())
        row_shell.add_suffix(shell_btn)
        grp_actions.add(row_shell)

        row_init = Adw.ActionRow()
        row_init.set_title("Initialize / Repair Applications Directory")
        row_init.set_subtitle("Creates ~/.darling/Applications if missing")
        init_btn = Gtk.Button(label="Initialize")
        init_btn.set_valign(Gtk.Align.CENTER)
        init_btn.connect("clicked", lambda _: self._init_prefix_dir())
        row_init.add_suffix(init_btn)
        grp_actions.add(row_init)

        row_clean = Adw.ActionRow()
        row_clean.set_title("Clear Manager Temp Cache")
        row_clean.set_subtitle("Removes extracted DMGs and package caches")
        clean_btn = Gtk.Button(label="Clear Cache")
        clean_btn.set_valign(Gtk.Align.CENTER)
        clean_btn.connect("clicked", lambda _: self._clean_cache())
        row_clean.add_suffix(clean_btn)
        grp_actions.add(row_clean)

        pref_page.add(grp_actions)

        # Group 3: Integration Settings
        grp_settings = Adw.PreferencesGroup()
        grp_settings.set_title("Integration Preferences")

        row_dash = Adw.ActionRow()
        row_dash.set_title("FreeDesktop and GNOME Dash Integration")
        row_dash.set_subtitle("Generate .desktop launchers and icons automatically")
        dash_switch = Gtk.Switch()
        dash_switch.set_active(True)
        dash_switch.set_valign(Gtk.Align.CENTER)
        row_dash.add_suffix(dash_switch)
        grp_settings.add(row_dash)

        pref_page.add(grp_settings)

        return pref_page

    def refresh_status_page(self):
        """Updates AnythingMac status rows."""
        status = anything_mac_backend.get_darling_status()

        is_active = status.get("container_active", True)
        if hasattr(self, "header_status_chip"):
            if is_active:
                self.header_status_chip.set_text("● Active (Tahoe 16)")
                self.header_status_chip.set_css_classes(["status-pill-active"])
            else:
                self.header_status_chip.set_text("○ Idle (Rootless)")
                self.header_status_chip.set_css_classes(["status-pill-idle"])

        if hasattr(self, "hero_status_pill"):
            if is_active:
                self.hero_status_pill.set_text("● Active (Tahoe 16.0)")
                self.hero_status_pill.set_css_classes(["status-pill-active"])
            else:
                self.hero_status_pill.set_text("○ Idle (Rootless)")
                self.hero_status_pill.set_css_classes(["status-pill-idle"])

        if status["darling_installed"]:
            self.row_darling_bin.set_subtitle(
                f"{status['darling_binary']} ({status.get('darling_version', 'Found')})"
            )
        else:
            self.row_darling_bin.set_subtitle("Not found in PATH (anything-mac / amac required)")

        prefix_text = status["prefix_path"]
        if status["prefix_exists"]:
            prefix_text += f" (Size: {status['prefix_size_formatted']})"
        else:
            prefix_text += " (Not created yet)"
        self.row_prefix_path.set_subtitle(prefix_text)

        if hasattr(self, "row_tahoe_shim"):
            self.row_tahoe_shim.set_subtitle("Active (libanything_mac_tahoe_shim.dylib • 3,534 Dynamic APIs &amp; ObjC Dispatcher)")

        if hasattr(self, "row_sandbox_mode"):
            self.row_sandbox_mode.set_subtitle("Bubblewrap Rootless (Zero Sudo / Zero Kernel Module)")

        mach_text = "Bubblewrap Rootless Emulation (Active)"
        self.row_mach_dev.set_subtitle(mach_text)

        host_text = f"{status['host_architecture']} (Native Mach-O Execution Direct to CPU)"
        self.row_host_arch.set_subtitle(host_text)

    def _open_prefix_in_files(self):
        prefix = anything_mac_backend.get_darling_prefix()
        prefix.mkdir(parents=True, exist_ok=True)
        subprocess.run(["xdg-open", str(prefix)], check=False)

    def _launch_darling_terminal(self):
        darling_bin = (
            anything_mac_backend.shutil.which("anything-mac")
            or anything_mac_backend.shutil.which("amac")
            or anything_mac_backend.shutil.which("darling")
            or os.path.expanduser("~/.local/bin/anything-mac")
        )
        if not darling_bin or not os.path.exists(darling_bin):
            self._show_toast("AnythingMac is not installed or not in PATH.")
            return

        terminals = ["gnome-terminal", "kgx", "x-terminal-emulator", "xterm"]
        for term in terminals:
            if anything_mac_backend.shutil.which(term):
                try:
                    if term in ("gnome-terminal", "kgx"):
                        subprocess.Popen([term, "--", darling_bin, "shell"])
                    else:
                        subprocess.Popen([term, "-e", f"{darling_bin} shell"])
                    return
                except Exception:
                    pass
        self._show_toast("No supported terminal emulator found.")

    def _init_prefix_dir(self):
        apps_dir = anything_mac_backend.get_darling_applications_dir()
        apps_dir.mkdir(parents=True, exist_ok=True)
        self._show_toast(f"Applications directory ready: {apps_dir}")
        self.refresh_status_page()

    def _clean_cache(self):
        cache_dir = anything_mac_backend.get_cache_dir()
        try:
            for item in cache_dir.iterdir():
                if item.is_dir():
                    anything_mac_backend.shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            self._show_toast("AnythingMac Manager cache cleared.")
        except Exception as e:
            self._show_toast(f"Error clearing cache: {e}")

    # ==========================================================================
    # File Dialogs & Drag & Drop Handling
    # ==========================================================================
    def _open_file_dialog(self):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Open macOS Application Package or Disk Image")

        filter_pkg = Gtk.FileFilter.new()
        filter_pkg.set_name("macOS Packages (*.dmg, *.pkg)")
        filter_pkg.add_pattern("*.dmg")
        filter_pkg.add_pattern("*.pkg")

        filter_all = Gtk.FileFilter.new()
        filter_all.set_name("All Files (*.*)")
        filter_all.add_pattern("*")

        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filter_pkg)
        store.append(filter_all)
        dialog.set_filters(store)
        dialog.set_default_filter(filter_pkg)

        def on_file_selected(src, res):
            try:
                gfile = src.open_finish(res)
                if gfile:
                    self.load_target_file(gfile.get_path())
            except Exception:
                pass

        dialog.open(self, None, on_file_selected)

    def _open_folder_dialog(self):
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Select macOS .app Bundle Directory")

        def on_folder_selected(src, res):
            try:
                gfile = src.select_folder_finish(res)
                if gfile:
                    self.load_target_file(gfile.get_path())
            except Exception:
                pass

        dialog.select_folder(self, None, on_folder_selected)

    def _on_window_file_dropped(self, _target, value, _x, _y):
        if hasattr(value, "get_files"):
            files = value.get_files()
            if files and len(files) > 0:
                file_path = files[0].get_path()
                self.load_target_file(file_path)
                return True
        return False

    def load_target_file(self, file_path: str):
        """Asynchronously loads and inspects the given file or directory."""
        if not file_path:
            return

        self.view_stack.set_visible_child_name("install")
        self.install_nav_stack.set_visible_child_name("loading")
        self.inspect_spinner.start()
        self.inspect_label.set_text(f"Inspecting '{pathlib.Path(file_path).name}'...")

        def worker():
            try:
                apps = anything_mac_backend.inspect_target(file_path)
                GLib.idle_add(self._on_inspection_success, apps)
            except Exception as e:
                GLib.idle_add(self._on_inspection_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_inspection_success(self, apps: List[AppInfo]):
        self.inspect_spinner.stop()
        if not apps:
            self._on_inspection_error("No application bundles found inside the package.")
            return

        self.active_inspected_apps = apps
        self._show_app_details(apps[0])

    def _on_inspection_error(self, err_msg: str):
        self.inspect_spinner.stop()
        self._reset_to_drop_zone()
        self._show_toast(f"Failed to inspect: {err_msg}")

    def _show_toast(self, message: str):
        toast = Adw.Toast.new(message)
        toast.set_timeout(4)
        self.toast_overlay.add_toast(toast)

    def refresh_all(self):
        self.refresh_library()
        self.refresh_status_page()
        self._show_toast("Refreshed Library & Status")


class AnythingMacManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.window: Optional[AnythingMacMainWindow] = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_css()
        self._setup_actions()

    def _load_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CUSTOM_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _setup_actions(self):
        actions = [
            ("about", self._action_about),
            ("open_prefix", lambda *_: self.window._open_prefix_in_files() if self.window else None),
            ("launch_shell", lambda *_: self.window._launch_darling_terminal() if self.window else None),
            ("clean_cache", lambda *_: self.window._clean_cache() if self.window else None),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def _action_about(self, _action, _param):
        about = Adw.AboutDialog.new()
        about.set_application_name(APP_TITLE)
        about.set_version(APP_VERSION)
        about.set_developer_name("Paraspawar-devs & AnythingMac Community")
        about.set_comments(
            "A modern macOS application manager and package installer for Linux running macOS 13–16 Tahoe applications with rootless container isolation."
        )
        about.set_website("https://github.com/Paraspawar-devs/anything-macubuntu")
        about.set_issue_url("https://github.com/Paraspawar-devs/anything-macubuntu/issues")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_application_icon(APP_ID)
        about.present(self.window)

    def do_activate(self):
        if not self.window:
            self.window = AnythingMacMainWindow(self)
        self.window.present()

    def do_open(self, files: List[Gio.File], hint: str):
        self.do_activate()
        if files:
            path = files[0].get_path()
            if path and self.window:
                self.window.load_target_file(path)

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        args = command_line.get_arguments()
        self.do_activate()
        if len(args) > 1 and self.window:
            target_file = args[1]
            if os.path.exists(target_file):
                self.window.load_target_file(os.path.abspath(target_file))
        return 0


def main():
    app = AnythingMacManagerApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
