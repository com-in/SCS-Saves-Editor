"""Offline update checks: version ordering and release download validation."""
import unittest
import base64
import hashlib
from pathlib import Path
import struct
import tempfile
from unittest import mock

from _updates import REPOSITORY, UpdateMixin, release_update, version_tuple
from _self_update import validate_download, prepare_update_bat


def release(tag="v1.4.0"):
    base = f"https://github.com/{REPOSITORY}/releases"
    return {"tag_name": tag, "html_url": f"{base}/tag/{tag}", "body": "Release notes",
            "assets": [{"name": "SCS.exe", "state": "uploaded",
                        "browser_download_url": f"{base}/download/{tag}/SCS.exe"}]}


class UpdateTests(unittest.TestCase):
    def test_pending_update_does_not_launch_while_mod_task_runs(self):
        host = mock.Mock()
        host._pending_update = ("apply-update.bat", "SCS.exe.bak")
        host._mods_worker.isRunning.return_value = True
        with mock.patch('_updates.launch_update_bat') as launch, mock.patch('_updates.QMessageBox.warning'):
            self.assertFalse(UpdateMixin._launch_pending_update(host))
            launch.assert_not_called()

    def test_launch_failure_prevents_exit(self):
        host = mock.Mock()
        host._pending_update = ("apply-update.bat", "SCS.exe.bak")
        host._mods_worker = None
        with mock.patch('_updates.launch_update_bat', side_effect=OSError('access denied')), mock.patch('_updates.QMessageBox.warning'):
            self.assertFalse(UpdateMixin._launch_pending_update(host))

    def test_download_validation_rejects_html_truncation_and_wrong_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SCS.exe"
            data = bytearray(132)
            data[:2] = b"MZ"
            data[0x3C:0x40] = struct.pack("<I", 128)
            data[128:] = b"PE\0\0"
            path.write_bytes(data)
            digest = "sha256:" + hashlib.sha256(data).hexdigest()
            validate_download(path, len(data), digest)
            for size, checksum in ((133, digest), (132, "sha256:" + "0" * 64)):
                with self.assertRaises(ValueError):
                    validate_download(path, size, checksum)
            path.write_bytes(b"<html>proxy error</html>")
            with self.assertRaises(ValueError):
                validate_download(path, path.stat().st_size)

    def test_bat_preserves_unicode_and_shell_characters_as_literal_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "中文 & (test) ! '"
            folder.mkdir()
            source = folder / "new.exe"
            target = folder / "SCS.exe"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            bat, backup = prepare_update_bat(source, target, 12345)
            text = bat.read_text(encoding="ascii")
            payload = text.split("-EncodedCommand ", 1)[1].splitlines()[0]
            script = base64.b64decode(payload).decode("utf-16le")
            self.assertIn(str(target).replace("'", "''"), script)
            self.assertIn("Get-Process -Id 12345", script)
            self.assertIn("WaitForExit(120000)", script)
            self.assertIn("[System.IO.File]::Copy($backup, $target, $false)", script)
            self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual(backup.parent, target.parent)
            self.assertFalse(backup.exists())
            self.assertLess(max(map(len, text.splitlines())), 8191)

    def test_versions_compare_numerically(self):
        self.assertGreater(version_tuple("v1.10.0"), version_tuple("1.9.9"))
        for invalid in ("", "latest", "1.2", "v1.2.3-beta", "1.2.3/evil"):
            with self.assertRaises(ValueError):
                version_tuple(invalid)

    def test_equal_and_older_releases_do_not_prompt(self):
        for tag in ("v1.4.0", "v1.3.0"):
            self.assertIsNone(release_update(release(tag), "1.4.0"))

    def test_newer_release_uses_uploaded_scs_exe(self):
        update = release_update(release("v1.10.0"), "1.4.0")
        self.assertEqual(update["tag"], "v1.10.0")
        self.assertTrue(update["download"].endswith("/v1.10.0/SCS.exe"))

    def test_drafts_and_prereleases_do_not_prompt(self):
        for flag in ("draft", "prerelease"):
            data = release()
            data[flag] = True
            self.assertIsNone(release_update(data, "1.3.0"))

    def test_no_uploaded_executable_falls_back_to_release_page(self):
        data = release()
        data["assets"][0]["state"] = "new"
        update = release_update(data, "1.3.0")
        self.assertEqual(update["download"], "")
        self.assertTrue(update["page"].endswith("/tag/v1.4.0"))

    def test_rejects_untrusted_download_and_page_urls(self):
        for field in ("page", "download"):
            data = release()
            if field == "page":
                data["html_url"] = "https://example.com/tag/v1.4.0"
            else:
                data["assets"][0]["browser_download_url"] = "https://example.com/SCS.exe"
            with self.assertRaises(ValueError):
                release_update(data, "1.3.0")
