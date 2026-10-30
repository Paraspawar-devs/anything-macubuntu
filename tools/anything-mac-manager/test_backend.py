#!/usr/bin/env python3
"""
Unit and integration tests for Darling App Manager backend.
"""

import gzip
import os
import pathlib
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

# Import backend under test
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anything_mac_backend


class TestDarlingBackend(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="darling_test_")
        self.test_path = pathlib.Path(self.test_dir)
        # Mock ANYTHING_MAC_PREFIX for testing
        self.mock_prefix = self.test_path / "mock_darling"
        self.mock_prefix.mkdir()
        os.environ["ANYTHING_MAC_PREFIX"] = str(self.mock_prefix)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if "ANYTHING_MAC_PREFIX" in os.environ:
            del os.environ["ANYTHING_MAC_PREFIX"]

    def create_dummy_macho(self, arch_types: list[str]) -> bytes:
        """Constructs synthetic Mach-O binary data."""
        if len(arch_types) == 1:
            arch = arch_types[0]
            # Thin binary
            cputype = 0x01000007 if arch == "x86_64" else (0x0100000C if arch == "arm64" else 7)
            # Little endian thin 64-bit Mach-O
            return struct.pack("<IIII", 0xFEEDFACF, cputype, 3, 2)
        else:
            # Fat binary (big endian)
            header = struct.pack(">II", 0xCAFEBABE, len(arch_types))
            arch_records = bytearray()
            offset = 4096
            for arch in arch_types:
                cputype = 0x01000007 if arch == "x86_64" else 0x0100000C
                arch_records.extend(struct.pack(">IIIII", cputype, 3, offset, 2048, 12))
                offset += 4096
            return header + bytes(arch_records)

    def create_dummy_app(self, app_name: str, bundle_id: str, archs: list[str]) -> pathlib.Path:
        """Creates a synthetic .app bundle directory tree."""
        app_dir = self.test_path / f"{app_name}.app"
        contents = app_dir / "Contents"
        macos = contents / "MacOS"
        resources = contents / "Resources"
        macos.mkdir(parents=True)
        resources.mkdir(parents=True)

        # Write Info.plist
        plist_data = {
            "CFBundleName": app_name,
            "CFBundleDisplayName": f"{app_name} macOS",
            "CFBundleIdentifier": bundle_id,
            "CFBundleShortVersionString": "2.4.1",
            "CFBundleVersion": "241",
            "CFBundleExecutable": app_name,
            "LSMinimumSystemVersion": "10.14.0",
            "CFBundleIconFile": "AppIcon",
        }
        with open(contents / "Info.plist", "wb") as f:
            plistlib.dump(plist_data, f)

        # Write Mach-O executable
        macho_bytes = self.create_dummy_macho(archs)
        exe_file = macos / app_name
        exe_file.write_bytes(macho_bytes)
        exe_file.chmod(0o755)

        return app_dir

    def test_macho_parsing_thin_x86_64(self):
        bin_path = self.test_path / "test_x86_64"
        bin_path.write_bytes(self.create_dummy_macho(["x86_64"]))
        archs = anything_mac_backend.parse_macho_architectures(bin_path)
        self.assertEqual(archs, ["x86_64"])

    def test_macho_parsing_universal_2(self):
        bin_path = self.test_path / "test_universal"
        bin_path.write_bytes(self.create_dummy_macho(["x86_64", "arm64"]))
        archs = anything_mac_backend.parse_macho_architectures(bin_path)
        self.assertEqual(set(archs), {"x86_64", "arm64"})
        summary, is_compat, badge = anything_mac_backend.format_arch_summary(archs)
        self.assertIn("Universal 2", summary)
        self.assertTrue(is_compat)
        self.assertEqual(badge, "badge-compat")

    def test_app_bundle_inspection(self):
        app_dir = self.create_dummy_app("CotEditor", "com.coteditor.CotEditor", ["x86_64"])
        info = anything_mac_backend.inspect_app_bundle(app_dir)

        self.assertEqual(info.bundle_name, "CotEditor")
        self.assertEqual(info.display_name, "CotEditor macOS")
        self.assertEqual(info.bundle_id, "com.coteditor.CotEditor")
        self.assertEqual(info.version, "2.4.1")
        self.assertEqual(info.architectures, ["x86_64"])
        self.assertTrue(info.is_darling_compatible)
        self.assertIn("10.14", info.min_os_display)
        self.assertIn("Mojave", info.min_os_display)
        self.assertFalse(info.is_installed)
        self.assertIsNotNone(info.icon_preview_path)
        self.assertTrue(os.path.exists(info.icon_preview_path))

    def test_installation_and_uninstallation(self):
        app_dir = self.create_dummy_app("SampleCalc", "com.apple.calc", ["x86_64", "arm64"])
        info = anything_mac_backend.inspect_app_bundle(app_dir)

        # 1. Install
        success, msg = anything_mac_backend.install_app(info)
        self.assertTrue(success, f"Install failed: {msg}")

        # Verify installed path
        installed_apps = anything_mac_backend.list_installed_apps()
        self.assertEqual(len(installed_apps), 1)
        self.assertEqual(installed_apps[0].bundle_name, "SampleCalc")
        self.assertTrue(installed_apps[0].is_installed)

        # Verify .desktop file
        desktop_file = (
            pathlib.Path("~/.local/share/applications").expanduser()
            / "darling-com.apple.calc.desktop"
        )
        self.assertTrue(desktop_file.is_file())
        desktop_content = desktop_file.read_text()
        self.assertIn("SampleCalc", desktop_content)
        self.assertIn("darling launch", desktop_content)

        # 2. Uninstall
        uninst_success, uninst_msg = anything_mac_backend.uninstall_app(info)
        self.assertTrue(uninst_success, f"Uninstall failed: {uninst_msg}")

        # Verify removal
        self.assertEqual(len(anything_mac_backend.list_installed_apps()), 0)
        self.assertFalse(desktop_file.exists())

    def test_pkg_xar_extraction(self):
        # Create a dummy .app and pack it into synthetic PKG (XAR)
        app_dir = self.create_dummy_app("InstallerApp", "org.darling.installer", ["x86_64"])

        # Create cpio archive of the app
        cpio_proc = subprocess.run(
            ["cpio", "-o", "-H", "newc"],
            input="InstallerApp.app\nInstallerApp.app/Contents\nInstallerApp.app/Contents/Info.plist\n".encode("utf-8"),
            cwd=str(self.test_path),
            capture_output=True,
            check=True,
        )
        payload_gz = gzip.compress(cpio_proc.stdout)

        # Synthetic XAR
        import zlib
        toc_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xar>
  <toc>
    <file id="1">
      <name>Payload</name>
      <type>file</type>
      <data>
        <offset>0</offset>
        <length>{len(payload_gz)}</length>
        <size>{len(cpio_proc.stdout)}</size>
        <encoding style="application/x-gzip"/>
      </data>
    </file>
  </toc>
</xar>""".encode("utf-8")

        toc_comp = zlib.compress(toc_xml)
        header = struct.pack(">4sHHQQI", b"xar!", 28, 1, len(toc_comp), len(toc_xml), 1)
        pkg_path = self.test_path / "TestInstaller.pkg"
        pkg_path.write_bytes(header + toc_comp + payload_gz)

        # Test extraction
        extract_dir = self.test_path / "pkg_out"
        extract_dir.mkdir()
        found = anything_mac_backend.extract_pkg_xar_python(pkg_path, extract_dir)
        self.assertTrue(len(found) >= 1)
        self.assertEqual(found[0].name, "InstallerApp.app")

    def test_udif_dmg_python_unpack(self):
        # Create synthetic UDIF DMG
        data_blob = b"Hello macOS DMG Filesystem" * 50
        compressed = zlib.compress(data_blob)
        comp_len = len(compressed)

        chunk_desc = struct.pack(">IIQQQQ", 0x80000005, 0, 0, (len(data_blob) + 511) // 512, 0, comp_len)
        term_desc = struct.pack(">IIQQQQ", 0xFFFFFFFE, 0, 0, 0, 0, 0)

        mish_header = bytearray(204)
        struct.pack_into(">4sIQQQII", mish_header, 0, b"mish", 1, 0, (len(data_blob) + 511) // 512, 0, 0, 2)
        mish_blob = bytes(mish_header) + chunk_desc + term_desc

        plist_obj = {
            "resource-fork": {
                "blkx": [{"Attributes": "0x0000", "CFName": "Apple_HFS", "Data": mish_blob}]
            }
        }
        xml_data = plistlib.dumps(plist_obj)

        xml_offset = comp_len
        xml_length = len(xml_data)

        koly = bytearray(512)
        koly[0:4] = b"koly"
        struct.pack_into(">I", koly, 4, 4)
        struct.pack_into(">I", koly, 8, 512)
        struct.pack_into(">Q", koly, 216, xml_offset)
        struct.pack_into(">Q", koly, 224, xml_length)

        dmg_bytes = compressed + xml_data + bytes(koly)
        dmg_path = self.test_path / "test.dmg"
        dmg_path.write_bytes(dmg_bytes)

        out_dir = self.test_path / "dmg_out"
        out_dir.mkdir()
        anything_mac_backend.decompress_udif_dmg_python(dmg_path, out_dir)
        raw_fs = out_dir / "extracted_fs.raw"
        self.assertTrue(raw_fs.is_file())
        self.assertEqual(raw_fs.read_bytes(), data_blob)

    def test_launch_rejection_for_arm64_on_x86_64(self):
        arm_app = self.create_dummy_app("AppleOnlyApp", "com.example.appleonly", ["arm64"])
        info = anything_mac_backend.inspect_app_bundle(arm_app)
        self.assertFalse(info.is_darling_compatible)
        success, msg = anything_mac_backend.launch_app(info)
        self.assertFalse(success)
        self.assertIn("Apple Silicon", msg)

    def test_uninstall_app_removes_bundle_and_desktop_file(self):
        dummy_app = self.create_dummy_app("TestUninstallApp", "com.example.uninstall", ["x86_64"])
        info = anything_mac_backend.inspect_app_bundle(dummy_app)
        install_ok, _ = anything_mac_backend.install_app(info)
        self.assertTrue(install_ok)
        installed_p = pathlib.Path(info.installed_path)
        desktop_p = pathlib.Path(info.desktop_file_path)
        self.assertTrue(installed_p.exists())
        self.assertTrue(desktop_p.exists())

        uninstall_ok, msg = anything_mac_backend.uninstall_app(info)
        self.assertTrue(uninstall_ok)
        self.assertFalse(installed_p.exists())
        self.assertFalse(desktop_p.exists())
        self.assertFalse(info.is_installed)

    def test_macos_version_check(self):
        compat, _ = anything_mac_backend.is_macos_version_supported("11.0.0")
        self.assertTrue(compat)
        compat_old, _ = anything_mac_backend.is_macos_version_supported("10.15.7")
        self.assertTrue(compat_old)
        compat_new, reason = anything_mac_backend.is_macos_version_supported("13.0.0")
        self.assertTrue(compat_new)
        self.assertIn("will attempt", reason)



if __name__ == "__main__":
    unittest.main()
