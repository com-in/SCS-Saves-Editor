"""Embed the release tag in the application before PyInstaller runs."""
import os
from pathlib import Path
import re

tag = os.environ.get("GITHUB_REF_NAME", "")
if os.environ.get("GITHUB_REF_TYPE") == "tag":
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise SystemExit("Release tag must have the form v1.2.3")
    Path("_version.py").write_text(
        f'"""Application version stamped by release CI."""\nAPP_VERSION = "{tag[1:]}"\n',
        encoding="utf-8")
    print("Embedded application version:", tag)
