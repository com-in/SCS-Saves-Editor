"""Offline tests for the mod installer helpers (no game directory is touched)."""
import os
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

import _mods_page as mods
from _mods_page import (
    ModsPageMixin, _plan_entry_map, _safe_join, _scan_plugin_entries,
    _is_probably_root, _unity_backend, _human_size, _is_bepinex_package,
    _plugin_names_in_archive, _coerce_game_root, _looks_like_game_root,
    _detect_game_roots, _parse_vdf_paths, _direct_mod_url_info,
    DEFAULT_MANIFEST_URL,
)


class _Installer(ModsPageMixin):
    """Minimal host so the pure helpers can run without building widgets."""


def _make_game_root(base):
    """Create a fake Unity install root containing Game_Data/Managed."""
    root = os.path.join(base, "game")
    os.makedirs(os.path.join(root, "Game_Data", "Managed"))
    return root


def _write_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


class ModPlanTests(unittest.TestCase):
    """Archive layout detection and destination mapping."""

    def test_online_manifest_default_is_configured_url(self):
        self.assertEqual(DEFAULT_MANIFEST_URL, "https://scsed.ctfun.top/mods_index.json")

    def test_bepinex_layout(self):
        plans = _plan_entry_map(["BepInEx/plugins/Foo/Foo.dll", "BepInEx/plugins/Foo/config.cfg"])
        self.assertEqual(plans["BepInEx/plugins/Foo/Foo.dll"], "Foo/Foo.dll")
        self.assertEqual(plans["BepInEx/plugins/Foo/config.cfg"], "Foo/config.cfg")

    def test_plugins_layout(self):
        plans = _plan_entry_map(["plugins/Bar.dll"])
        self.assertEqual(plans["plugins/Bar.dll"], "Bar.dll")

    def test_bare_dll(self):
        plans = _plan_entry_map(["Loose.dll"])
        self.assertEqual(plans["Loose.dll"], "Loose.dll")

    def test_wrapper_folder_is_stripped(self):
        plans = _plan_entry_map(["Wrapper-v1/Plugin.dll", "Wrapper-v1/README.txt"])
        self.assertEqual(plans["Wrapper-v1/Plugin.dll"], "Plugin.dll")

    def test_empty_or_junk_archive(self):
        self.assertIsNone(_plan_entry_map([]))
        self.assertIsNone(_plan_entry_map(["__MACOSX/.DS_Store"]))

    def test_archive_without_dll_is_rejected(self):
        # A random zip must never be copied into the plugins folder.
        self.assertIsNone(_plan_entry_map(["src/bin/note.txt"]))
        self.assertIsNone(_plan_entry_map(["Wrapper/notes.txt"]))

    def test_wrapper_with_dll_is_kept(self):
        self.assertEqual(_plan_entry_map(["Wrapper/note.txt", "Wrapper/P.dll"]),
                         {"Wrapper/note.txt": "note.txt", "Wrapper/P.dll": "P.dll"})

    def test_bepinex_package_detection(self):
        self.assertTrue(_is_bepinex_package(["BepInEx/plugins/F/F.dll"]))
        self.assertTrue(_is_bepinex_package(["BepInEx/patchers/P.dll"]))
        self.assertFalse(_is_bepinex_package(["plugins/F.dll"]))

    def test_plugin_names_from_package(self):
        names = _plugin_names_in_archive(
            ["BepInEx/core/x.dll", "BepInEx/plugins/F/F.dll", "BepInEx/plugins/G.dll"])
        self.assertEqual(names, ["F", "G.dll"])


class ModSafetyTests(unittest.TestCase):
    """Path containment helpers."""

    def test_safe_join_allows_child(self):
        self.assertTrue(_safe_join(r"C:\game\Plugins", "Foo/Foo.dll").endswith("Foo\\Foo.dll"))

    def test_safe_join_rejects_escape(self):
        self.assertIsNone(_safe_join(r"C:\game\Plugins", "../evil.dll"))
        self.assertIsNone(_safe_join(r"C:\game\Plugins", r"..\..\Windows\evil.dll"))

    def test_human_size_units(self):
        self.assertEqual(_human_size(512), "512 B")
        self.assertEqual(_human_size(2048), "2.0 KB")
        self.assertEqual(_human_size(5 * 1024 * 1024), "5.0 MB")

    def test_direct_mod_url_validation(self):
        self.assertEqual(
            _direct_mod_url_info("https://example.test/Foo.dll?download=1"),
            ("https://example.test/Foo.dll?download=1", "Foo.dll", ".dll"))
        self.assertEqual(_direct_mod_url_info("http://example.test/mod.zip")[2], ".zip")
        for url in ("", "file:///tmp/Foo.dll", "https://example.test/page.html"):
            with self.assertRaises(ValueError):
                _direct_mod_url_info(url)


class ModLocateTests(unittest.TestCase):
    """Game directory locating: manual coercion and auto-detection."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="scs_mods_locate_")
        # Typical Steam layout: <base>/steamapps/common/<game>/<game>_Data
        self.root = os.path.join(self.base, "steamapps", "common",
                                 "Scam Center Simulator UnderKingdom")
        self.data = os.path.join(self.root, "Scam Center Simulator UnderKingdom_Data")
        os.makedirs(os.path.join(self.data, "Managed"))
        os.makedirs(os.path.join(self.data, "Plugins"))
        with open(os.path.join(self.root, "Scam Center Simulator UnderKingdom.exe"), "w"):
            pass
        # An unrelated Unity game that must never be picked up.
        self.other = os.path.join(self.base, "steamapps", "common", "Some Other Game")
        os.makedirs(os.path.join(self.other, "Some Other Game_Data", "Managed"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_manual_pick_is_coerced_to_root(self):
        self.assertEqual(_coerce_game_root(self.root), self.root)
        self.assertEqual(_coerce_game_root(self.data), self.root)
        self.assertEqual(_coerce_game_root(os.path.join(self.data, "Managed")), self.root)
        self.assertEqual(_coerce_game_root(os.path.join(self.data, "Plugins")), self.root)

    def test_manual_pick_rejects_unrelated_folder(self):
        self.assertEqual(_coerce_game_root(os.path.join(self.base, "steamapps")), "")

    def test_name_match_is_selective(self):
        self.assertTrue(_looks_like_game_root(self.root))
        self.assertFalse(_looks_like_game_root(self.other))
        self.assertTrue(_is_probably_root(self.other))   # still a Unity root

    def test_auto_detect_finds_only_this_game(self):
        with mock.patch.object(mods, "_steam_library_roots",
                               return_value=[os.path.join(self.base, "steamapps", "common")]), \
             mock.patch.object(mods, "_default_game_roots", return_value=[]), \
             mock.patch.object(mods, "find_game_process", return_value=(None, None)):
            roots = _detect_game_roots()
        self.assertEqual(roots, [self.root])
        self.assertNotIn(self.other, roots)

    def test_auto_detect_uses_running_process(self):
        with mock.patch.object(mods, "find_game_process", return_value=(4242, "UnderKingdom.exe")), \
             mock.patch.object(mods, "_process_image_path",
                               return_value=os.path.join(self.root, "UnderKingdom.exe")), \
             mock.patch.object(mods, "_steam_library_roots", return_value=[]), \
             mock.patch.object(mods, "_default_game_roots", return_value=[]):
            self.assertEqual(_detect_game_roots(), [self.root])

    def test_auto_detect_handles_nested_install(self):
        nested = os.path.join(self.base, "epic", "Scam Center Simulator", "UnderKingdom")
        os.makedirs(os.path.join(nested, "UnderKingdom_Data", "Managed"))
        with mock.patch.object(mods, "_steam_library_roots", return_value=[]), \
             mock.patch.object(mods, "_default_game_roots",
                               return_value=[os.path.join(self.base, "epic")]), \
             mock.patch.object(mods, "find_game_process", return_value=(None, None)):
            self.assertIn(nested, _detect_game_roots())

    def test_steam_vdf_parsing(self):
        vdf = os.path.join(self.base, "libraryfolders.vdf")
        with open(vdf, "w", encoding="utf-8") as handle:
            handle.write('"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"C:\\\\Steam"\n\t}\n'
                         '\t"1"\n\t{\n\t\t"path"\t\t"D:\\\\Games"\n\t}\n}\n')
        self.assertIn(r"C:\Steam", _parse_vdf_paths(vdf))
        self.assertIn(r"D:\Games", _parse_vdf_paths(vdf))
        self.assertEqual(_parse_vdf_paths(os.path.join(self.base, "missing.vdf")), [])


class ModInstallTests(unittest.TestCase):
    """Extraction into a throwaway plugins folder."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="scs_mods_test_")
        self.root = _make_game_root(self.base)
        self.plugins = os.path.join(self.root, "BepInEx", "plugins")
        os.makedirs(self.plugins)
        self.tool = _Installer()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_root_detection_and_backend(self):
        self.assertTrue(_is_probably_root(self.root))
        self.assertFalse(_is_probably_root(os.path.join(self.base, "nope")))
        self.assertEqual(_unity_backend(self.root), "mono")

    def test_uninstall_loader_and_all_mods_preserves_game_files(self):
        archive = _write_zip(os.path.join(self.base, "loader.zip"), {
            "BepInEx/plugins/Foo.dll": "mod",
            "BepInEx/plugins/disabled/Bar.dll": "disabled",
            "BepInEx/config/Foo.cfg": "config",
            "doorstop_config.ini": "targetAssembly=BepInEx/core/BepInEx.Preloader.dll",
            "winhttp.dll": "doorstop",
            "version.dll": "unrelated game library",
            "Game.exe": "game",
        })
        with zipfile.ZipFile(archive) as source:
            self.tool._extract_all(source, self.root, source.namelist())
        self.tool._mods_root = lambda: self.root
        self.tool._mods_is_busy = lambda: False
        self.tool._mods_game_running = lambda: False
        self.tool._mods_online_rows = []
        self.tool._mods_refresh_loader = mock.Mock()
        self.tool._mods_refresh_installed = mock.Mock()
        self.tool._mods_ok = mock.Mock()
        self.tool._mods_fail = mock.Mock()
        with mock.patch.object(mods.QMessageBox, "question", return_value=mods.QMessageBox.No):
            self.tool._mods_uninstall_bepinex()
        self.assertTrue(os.path.exists(self.plugins))
        with mock.patch.object(mods.QMessageBox, "question", return_value=mods.QMessageBox.Yes):
            self.tool._mods_uninstall_bepinex()
        self.assertFalse(os.path.exists(os.path.join(self.root, "BepInEx")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "winhttp.dll")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "doorstop_config.ini")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "Game.exe")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "version.dll")))
        self.tool._mods_fail.assert_not_called()

    def test_install_bepinex_layout_archive(self):
        archive = _write_zip(os.path.join(self.base, "a.zip"),
                             {"BepInEx/plugins/Foo/Foo.dll": "dll"})
        names = self.tool._extract_mod_archive(archive, self.root)
        self.assertEqual(names, ["Foo"])
        self.assertTrue(os.path.isfile(os.path.join(self.plugins, "Foo", "Foo.dll")))

    def test_install_bare_dll_archive(self):
        archive = _write_zip(os.path.join(self.base, "b.zip"), {"Bar.dll": "dll"})
        names = self.tool._extract_mod_archive(archive, self.root)
        self.assertEqual(names, ["Bar.dll"])
        self.assertTrue(os.path.isfile(os.path.join(self.plugins, "Bar.dll")))

    def test_patcher_package_keeps_its_folder(self):
        archive = _write_zip(os.path.join(self.base, "p.zip"),
                             {"BepInEx/patchers/Pre.dll": "dll"})
        names = self.tool._extract_mod_archive(archive, self.root)
        self.assertEqual(names, ["BepInEx"])
        self.assertTrue(os.path.isfile(os.path.join(self.root, "BepInEx", "patchers", "Pre.dll")))

    def test_archive_without_plugin_is_rejected(self):
        archive = _write_zip(os.path.join(self.base, "junk.zip"), {"notes/readme.txt": "x"})
        with self.assertRaises(RuntimeError):
            self.tool._extract_mod_archive(archive, self.root)
        self.assertFalse(os.path.exists(os.path.join(self.plugins, "notes")))

    def test_zip_slip_is_rejected(self):
        archive = _write_zip(os.path.join(self.base, "evil.zip"),
                             {"BepInEx/plugins/../../../escaped.dll": "dll"})
        with self.assertRaises(RuntimeError):
            self.tool._extract_mod_archive(archive, self.root)
        self.assertFalse(os.path.exists(os.path.join(self.root, "escaped.dll")))

    def test_zip_slip_does_not_partially_install(self):
        archive = _write_zip(os.path.join(self.base, "mixed-evil.zip"), {
            "BepInEx/plugins/Good.dll": "dll",
            "BepInEx/plugins/../../../escaped.dll": "evil",
        })
        with self.assertRaises(RuntimeError):
            self.tool._extract_mod_archive(archive, self.root)
        self.assertFalse(os.path.exists(os.path.join(self.plugins, "Good.dll")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "escaped.dll")))

    def test_non_zip_is_rejected(self):
        path = os.path.join(self.base, "not.zip")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("plain")
        with self.assertRaises(RuntimeError):
            self.tool._extract_mod_archive(path, self.root)

    def test_scan_plugin_entries_filters_noise(self):
        os.makedirs(os.path.join(self.plugins, "FolderMod"))
        with open(os.path.join(self.plugins, "FolderMod", "mod.dll"), "w") as handle:
            handle.write("x")
        with open(os.path.join(self.plugins, "Loose.dll"), "w") as handle:
            handle.write("x")
        with open(os.path.join(self.plugins, "readme.txt"), "w") as handle:
            handle.write("x")
        names = [row[0] for row in _scan_plugin_entries(self.plugins)]
        self.assertEqual(sorted(names), ["FolderMod", "Loose.dll"])
        disabled = os.path.join(self.plugins, "disabled")
        os.makedirs(disabled)
        self.assertEqual(_scan_plugin_entries(disabled), [])

    def test_entry_size_and_missing_dir(self):
        self.assertEqual(_scan_plugin_entries(os.path.join(self.base, "missing")), [])


if __name__ == "__main__":
    unittest.main()
