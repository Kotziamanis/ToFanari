# -*- coding: utf-8 -*-
"""ToFanari — Automated build workflow. Increments version, installs deps, builds .exe."""

import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
BUILD_VERSION_FILE = os.path.join(SCRIPT_DIR, "BUILD_VERSION")
BUILDS_DIR = os.path.join(SCRIPT_DIR, "builds")
PROJECT_NAME = "tofanari"


def get_next_version() -> int:
    """Read current version, increment, save, return new version."""
    path = BUILD_VERSION_FILE
    try:
        with open(path, "r") as f:
            current = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        current = 4
    next_ver = current + 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(str(next_ver) + "\n")
    return next_ver


def install_dependencies():
    """Install pymupdf, openpyxl, PyInstaller (idempotent)."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pymupdf", "openpyxl", "PyInstaller", "-q"],
        cwd=SCRIPT_DIR,
        check=True,
    )


def build_exe(version: int) -> str:
    """
    Run PyInstaller to create a fresh executable, then copy into builds/tofanari_v{version}/.
    Returns absolute path to builds/tofanari_v{version}/tofanari.exe
    """
    version_dir = f"{PROJECT_NAME}_v{version}"
    distpath = os.path.abspath(os.path.join(BUILDS_DIR, version_dir))
    workpath = os.path.abspath(os.path.join(SCRIPT_DIR, "build", version_dir))
    spec_file = os.path.join(SCRIPT_DIR, "tofanari.spec")

    if os.path.isdir(distpath):
        shutil.rmtree(distpath)
    os.makedirs(distpath, exist_ok=True)
    os.makedirs(workpath, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            f"--distpath={distpath}",
            f"--workpath={workpath}",
            spec_file,
        ],
        cwd=SCRIPT_DIR,
        check=True,
    )

    exe_src = os.path.join(distpath, "ToFanari", "ToFanari.exe")
    internal_src = os.path.join(distpath, "ToFanari", "_internal")
    exe_dst = os.path.join(distpath, "tofanari.exe")
    internal_dst = os.path.join(distpath, "_internal")

    if not os.path.isfile(exe_src):
        raise SystemExit(f"PyInstaller did not create executable at: {exe_src}")

    if os.path.isfile(exe_dst):
        os.remove(exe_dst)
    shutil.copy2(exe_src, exe_dst)

    if os.path.isdir(internal_src):
        if os.path.isdir(internal_dst):
            shutil.rmtree(internal_dst)
        shutil.copytree(internal_src, internal_dst)

    shutil.rmtree(os.path.join(distpath, "ToFanari"), ignore_errors=True)

    if os.path.isdir(workpath):
        shutil.rmtree(workpath, ignore_errors=True)

    if not os.path.isfile(exe_dst):
        raise SystemExit(f"Failed to create final executable at: {exe_dst}")

    return os.path.abspath(exe_dst)


def main():
    print("ToFanari — Build New Version")
    print("-" * 40)
    version = get_next_version()
    print(f"Version: {PROJECT_NAME}_v{version}")
    print("Installing dependencies...")
    install_dependencies()
    print("Building executable...")
    exe_path = build_exe(version)
    print("-" * 40)
    print("BUILD COMPLETE")
    print(f"Executable: {exe_path}")
    print(f"Run: {exe_path}")


if __name__ == "__main__":
    main()
