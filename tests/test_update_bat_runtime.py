"""Windows integration tests: execute the real updater against disposable EXEs."""
import os
import ctypes
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from _self_update import launch_update_bat, prepare_update_bat


CSC = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"


@unittest.skipUnless(os.name == "nt" and CSC.is_file(), "Requires Windows and the .NET C# compiler")
class BatRuntimeTests(unittest.TestCase):
    def wait_until(self, condition, description):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.1)
        self.fail("Timed out: " + description)

    def run_update(self, fail_copy=False):
        with tempfile.TemporaryDirectory(prefix="scs_bat_test_") as directory:
            folder = Path(directory) / "中文 & (test) ! '"
            folder.mkdir()
            code = folder / "Fixture.cs"
            code.write_text('''using System;
using System.IO;
using System.Threading;
class Fixture {
    static void Main(string[] args) {
        if (args.Length > 0) {
            File.WriteAllText(args[0] + ".ready", "ready");
            while (!File.Exists(args[0])) Thread.Sleep(50);
            return;
        }
#if NEW
        string version = "new";
#else
        string version = "old";
#endif
        File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "launched.pid"), System.Diagnostics.Process.GetCurrentProcess().Id.ToString());
        File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "launched.txt"), version);
    }
}''', encoding="utf-8")
            target, source = folder / "SCS.exe", folder / "new.exe"
            for path, defines in ((target, []), (source, ["/define:NEW"])):
                subprocess.run([str(CSC), "/nologo", "/target:winexe", "/out:" + str(path),
                                *defines, str(code)], check=True, capture_output=True)
            old_bytes, new_bytes = target.read_bytes(), source.read_bytes()
            gate = folder / "exit.signal"
            old = subprocess.Popen([str(target), str(gate)])
            try:
                self.wait_until(lambda: Path(str(gate) + ".ready").exists(), "old process ready")
                bat, backup = prepare_update_bat(source, target, old.pid)
                if fail_copy:
                    source.unlink()
                helper = launch_update_bat(bat)
                time.sleep(2)
                self.assertIsNone(old.poll())
                self.assertFalse(backup.exists(), "Must wait for the old process")
                self.assertEqual(target.read_bytes(), old_bytes)
                gate.touch()
                old.wait(timeout=5)
                self.assertEqual(helper.wait(timeout=25), 1 if fail_copy else 0)
                marker, log = folder / "launched.txt", folder / "update-error.log"
                self.wait_until(marker.exists, "replacement or restored executable launch")
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.OpenProcess.restype = ctypes.c_void_p
                kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                handle = kernel.OpenProcess(0x100000, False, int((folder / "launched.pid").read_text()))
                if handle:
                    try:
                        self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0)
                    finally:
                        kernel.CloseHandle(handle)
                self.assertEqual(marker.read_text(), "old" if fail_copy else "new")
                self.assertEqual(target.read_bytes(), old_bytes if fail_copy else new_bytes)
                self.assertEqual(backup.read_bytes(), old_bytes)
                if fail_copy:
                    self.wait_until(log.exists, "failure log")
                    self.assertTrue(log.read_text(encoding="utf-8"))
                else:
                    self.wait_until(lambda: not bat.exists(), "BAT self deletion")
                    self.assertFalse(source.exists())
                    self.assertFalse(log.exists())
            finally:
                if old.poll() is None:
                    gate.touch()
                    old.wait(timeout=5)

    def test_replace_restart_and_self_delete(self):
        self.run_update()

    def test_failed_copy_restores_and_restarts_old_executable(self):
        self.run_update(fail_copy=True)
