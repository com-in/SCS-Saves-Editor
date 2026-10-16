"""Prepare a detached BAT helper for replacing a packaged Windows executable."""
import base64
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import uuid


def validate_download(path, size, digest=""):
    """Reject incomplete downloads, HTML responses and non-PE executables."""
    path = Path(path)
    if size <= 0 or path.stat().st_size != size:
        raise ValueError("更新文件大小与 Release 不一致，请重新下载。")
    with path.open("rb") as handle:
        if handle.read(2) != b"MZ":
            raise ValueError("下载内容不是 Windows 程序，可能是代理错误页面。")
        handle.seek(0x3C)
        offset_bytes = handle.read(4)
        if len(offset_bytes) != 4:
            raise ValueError("更新文件头不完整。")
        offset = struct.unpack("<I", offset_bytes)[0]
        if offset > size - 4:
            raise ValueError("更新文件头无效。")
        handle.seek(offset)
        if handle.read(4) != b"PE\0\0":
            raise ValueError("更新文件不是有效的 PE 程序。")
        if digest:
            handle.seek(0)
            actual = hashlib.file_digest(handle, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else None
            if actual is None:
                hasher = hashlib.sha256()
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
                actual = hasher.hexdigest()
            if digest.lower() != "sha256:" + actual:
                raise ValueError("更新文件 SHA-256 校验失败，请重新下载。")


def prepare_update_bat(download, executable, pid):
    """Write a BAT with an encoded PowerShell payload; never interpolate paths into cmd code."""
    download, executable = Path(download).resolve(), Path(executable).resolve()
    if download == executable or not download.is_file() or not executable.is_file():
        raise ValueError("更新文件或程序路径无效。")
    bat = download.parent / "apply-update.bat"
    if any(char in str(bat) for char in ('%', '"', '\r', '\n')):
        raise ValueError("临时目录包含 BAT 不支持的字符，请使用手动下载更新。")
    backup = executable.with_name(executable.name + "." + uuid.uuid4().hex + ".bak")
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    # EncodedCommand preserves Unicode paths and prevents shell metacharacters
    # from becoming commands. Keep the old EXE until replacement and launch succeed.
    script = f"""$ErrorActionPreference = 'Stop'
$target = {quote(executable)}
$source = {quote(download)}
$backup = {quote(backup)}
$log = {quote(download.parent / 'update-error.log')}
$moved = $false
try {{
    $old = Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue
    if ($null -ne $old) {{
        if (-not $old.WaitForExit(120000)) {{ throw 'Timed out waiting for the application to exit.' }}
    }}
    $replaced = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {{
        try {{ [System.IO.File]::Move($target, $backup); $replaced = $true; break }}
        catch {{ Start-Sleep -Milliseconds 500 }}
    }}
    if (-not $replaced) {{ throw 'Cannot back up the executable. Check folder permissions or file locks.' }}
    $moved = $true
    [System.IO.File]::Copy($source, $target, $false)
    Start-Process -FilePath $target -WorkingDirectory ([System.IO.Path]::GetDirectoryName($target))
    try {{ [System.IO.File]::Delete($source) }} catch {{ }}
    exit 0
}} catch {{
    $message = $_.Exception.ToString()
    if ($moved) {{
        try {{
            if ([System.IO.File]::Exists($target)) {{ [System.IO.File]::Delete($target) }}
            [System.IO.File]::Copy($backup, $target, $false)
            Start-Process -FilePath $target -WorkingDirectory ([System.IO.Path]::GetDirectoryName($target))
        }} catch {{ $message += [Environment]::NewLine + $_.Exception.ToString() }}
    }}
    [System.IO.File]::WriteAllText($log, $message)
    exit 1
}}
"""
    payload = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    if len(payload) + 150 > 8191:
        raise ValueError("更新路径过长，无法启动 BAT，请使用手动下载更新。")
    bat.write_text(
        '@echo off\r\nsetlocal DisableDelayedExpansion\r\n'
        f'"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -NonInteractive -EncodedCommand {payload}\r\n'
        'if errorlevel 1 exit /b 1\r\n'
        'endlocal\r\n(goto) 2>nul & del "%~f0"\r\n', encoding="ascii", newline="")
    return bat, backup


def launch_update_bat(bat):
    cmd = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe")
    # cmd.exe uses different quoting from the C runtime. Passing a list would
    # turn the nested quotes into literal backslash-quote sequences.
    return subprocess.Popen(
        f'"{cmd}" /d /s /c ""{bat}""', executable=cmd,
        cwd=str(Path(bat).parent), close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
