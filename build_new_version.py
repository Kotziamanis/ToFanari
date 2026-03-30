# -*- coding: utf-8 -*-
"""Tofanari Main Tool — automated build workflow. Uses APP_VERSION from config, installs deps, builds .exe."""

import glob
import os
import shutil
import subprocess
import sys
import time
import zipfile

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")
DIST_DIR = os.path.join(SCRIPT_DIR, "dist")
RELEASE_DIR = os.path.join(SCRIPT_DIR, "release")
RELEASE_FOLDER = "TofanariMainTool"
EXPECTED_EXE = "TofanariMainTool.exe"


def get_version_from_config() -> str:
    """Read APP_VERSION from config.py. Single source of truth."""
    try:
        from config import APP_VERSION
        return APP_VERSION
    except ImportError:
        return "v1.0.0"


def _handle_rmtree_error(func, path, exc_info):
    """Log but ignore errors during rmtree (e.g. locked DLLs on Windows)."""
    print(f"  Warning: Could not remove {path}: {exc_info[1]}")

def clean_before_build() -> None:
    """Delete build/, dist/, release/, PyInstaller cache. Ensures no stale artifacts."""
    dirs_to_clean = [BUILD_DIR, DIST_DIR]
    release_folder = os.path.join(RELEASE_DIR, RELEASE_FOLDER)
    if os.path.isdir(release_folder):
        dirs_to_clean.append(release_folder)
    for d in dirs_to_clean:
        if os.path.isdir(d):
            try:
                shutil.rmtree(d, onerror=_handle_rmtree_error)
                print(f"  Deleted: {d}")
            except Exception as e:
                print(f"  Warning: Could not fully delete {d}: {e}")
    # Clear PyInstaller cache to force fresh analysis (fixes stale version)
    pyi_cache = os.environ.get("PYINSTALLER_CONFIG_DIR") or os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "pyinstaller"
    )
    if os.path.isdir(pyi_cache):
        try:
            shutil.rmtree(pyi_cache, onerror=_handle_rmtree_error)
            print(f"  Cleared PyInstaller cache: {pyi_cache}")
        except Exception as e:
            print(f"  Warning: Could not clear PyInstaller cache: {e}")
    for exe in glob.glob(os.path.join(SCRIPT_DIR, "*.exe")):
        try:
            os.remove(exe)
            print(f"  Deleted: {exe}")
        except OSError:
            pass


def install_dependencies():
    """Install pymupdf, openpyxl, PyInstaller (idempotent)."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pymupdf", "openpyxl", "PyInstaller", "-q"],
        cwd=SCRIPT_DIR,
        check=True,
    )


def build_exe(version: str) -> str:
    """
    Run PyInstaller to create a fresh executable.
    Uses --clean to avoid reusing old cache. Output: dist/TofanariMainTool/TofanariMainTool.exe (onedir)
    """
    spec_file = os.path.join(SCRIPT_DIR, "tofanari.spec")
    # Use dedicated workpath to avoid polluting project build/ (already cleaned)
    workpath = os.path.abspath(os.path.join(BUILD_DIR, "pyinstaller"))
    distpath = os.path.abspath(DIST_DIR)

    os.makedirs(workpath, exist_ok=True)
    os.makedirs(distpath, exist_ok=True)

    spec_path = os.path.abspath(os.path.join(SCRIPT_DIR, "tofanari.spec"))
    entry_file = os.path.abspath(os.path.join(SCRIPT_DIR, "app.py"))
    print(f"  Version (source): {version}")
    print(f"  Entry file: {entry_file}")
    print(f"  Spec file:  {spec_path}")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            f"--distpath={distpath}",
            f"--workpath={workpath}",
            spec_path,
        ],
        cwd=SCRIPT_DIR,
        check=True,
    )

    # Spec uses COLLECT (onedir): dist/TofanariMainTool/TofanariMainTool.exe + _internal/
    # Keep standard onedir structure - do NOT flatten (flattening can cause "Failed to start embedded python interpreter")
    output_dir = os.path.join(distpath, RELEASE_FOLDER)
    exe_path = os.path.join(output_dir, EXPECTED_EXE)

    if not os.path.isfile(exe_path):
        raise SystemExit(f"PyInstaller did not create executable at: {exe_path}")

    # Copy settings folder next to EXE (required at runtime)
    _copy_settings_to(output_dir)
    return os.path.abspath(exe_path)


def _copy_settings_to(dest_dir: str) -> None:
    """Copy parameters.json and bunny_credentials.json into dest_dir/settings/."""
    settings_src = os.path.join(SCRIPT_DIR, "settings")
    settings_dest = os.path.join(dest_dir, "settings")
    os.makedirs(settings_dest, exist_ok=True)
    for f in ["parameters.json", "bunny_credentials.json"]:
        src_f = os.path.join(settings_src, f)
        dst_f = os.path.join(settings_dest, f)
        if os.path.isfile(src_f):
            try:
                shutil.copy2(src_f, dst_f)
            except OSError as e:
                print(f"  Warning: Could not copy {f}: {e}")
        elif f == "parameters.json":
            # Ensure parameters.json exists (required)
            try:
                with open(dst_f, "w", encoding="utf-8") as out:
                    out.write('{"collections":[],"books":[],"schema_version":1}\n')
            except OSError:
                pass


def _create_desktop_shortcut_script(release_folder: str) -> None:
    """Create Create_Desktop_Shortcut.bat inside release folder."""
    bat_path = os.path.join(release_folder, "Create_Desktop_Shortcut.bat")
    # Use %~dp0 to get batch file's directory; PowerShell creates .lnk on Desktop
    content = r'''@echo off
title Tofanari Main Tool - Create Desktop Shortcut
set "FOLDER=%~dp0"
set "EXE=%FOLDER%TofanariMainTool.exe"
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $desk = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut($desk + '\TofanariMainTool.lnk'); $s.TargetPath = '%EXE%'; $s.WorkingDirectory = '%FOLDER:~0,-1%'; $s.Save(); Write-Host 'Shortcut created: Desktop\TofanariMainTool.lnk'"
echo.
echo Done. You can now launch Tofanari Main Tool from your Desktop.
pause
'''
    try:
        with open(bat_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(content)
    except OSError as e:
        print(f"  Warning: Could not create shortcut script: {e}")


def create_release_package(exe_path: str) -> str:
    """
    Create portable release: release/TofanariMainTool/ + TofanariMainTool_portable.zip.
    Returns path to release folder.
    """
    release_folder = os.path.join(RELEASE_DIR, RELEASE_FOLDER)
    zip_path = os.path.join(RELEASE_DIR, "TofanariMainTool_portable.zip")
    dist_folder = os.path.dirname(exe_path)

    # Clean and copy dist -> release/TofanariMainTool/
    if os.path.isdir(release_folder):
        try:
            shutil.rmtree(release_folder, onerror=_handle_rmtree_error)
        except Exception as e:
            print(f"  Warning: Could not remove {release_folder}: {e}")
    os.makedirs(RELEASE_DIR, exist_ok=True)
    try:
        shutil.copytree(dist_folder, release_folder)
    except OSError as e:
        raise SystemExit(f"Cannot create release folder: {e}")

    # Ensure settings in release
    _copy_settings_to(release_folder)

    # Create desktop shortcut script
    _create_desktop_shortcut_script(release_folder)

    # Create README with operator instructions
    readme_path = os.path.join(release_folder, "README.txt")
    version = get_version_from_config()
    try:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("Tofanari Main Tool — Portable Release\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Version: {version}\n\n")
            f.write("IMPORTANT: Do NOT copy TofanariMainTool.exe alone.\n")
            f.write("It requires the _internal/ folder and settings/ to run.\n\n")
            f.write("USAGE:\n")
            f.write("  1. Copy this ENTIRE 'TofanariMainTool' folder to your desired location,\n")
            f.write("     OR unzip TofanariMainTool_portable.zip.\n\n")
            f.write("  2. Run TofanariMainTool.exe from inside the folder.\n\n")
            f.write("  3. Optional: Run Create_Desktop_Shortcut.bat to add a desktop\n")
            f.write("     shortcut (points to the exe in this folder, does not copy it).\n\n")
            f.write("PORTABLE: This folder is self-contained. Copy the whole folder or\n")
            f.write("unzip TofanariMainTool_portable.zip on another PC and run from there.\n\n")
            f.write("If the app fails to start on a new PC, install Microsoft Visual C++\n")
            f.write("Redistributable (latest) from microsoft.com.\n")
    except OSError:
        pass

    # Create zip
    if os.path.isfile(zip_path):
        try:
            os.remove(zip_path)
        except OSError:
            pass
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(release_folder):
                for f in files:
                    fp = os.path.join(root, f)
                    arcname = os.path.relpath(fp, release_folder)
                    zf.write(fp, os.path.join(RELEASE_FOLDER, arcname))
    except OSError as e:
        print(f"  Warning: Could not create zip: {e}")

    return os.path.abspath(release_folder)


def _is_exe_locked(path: str) -> bool:
    """Return True if file exists and cannot be removed (locked by another process)."""
    if not os.path.isfile(path):
        return False
    try:
        os.remove(path)
        return False  # Removed, recreate later
    except OSError:
        return True


def main():
    print("Tofanari Main Tool — Build New Version")
    print("-" * 40)
    version = get_version_from_config()
    print(f"Building version: {version} (from config.APP_VERSION)")
    dist_exe = os.path.join(DIST_DIR, RELEASE_FOLDER, EXPECTED_EXE)
    if _is_exe_locked(dist_exe):
        print(f"ERROR: {dist_exe} is in use. Close TofanariMainTool.exe and retry.")
        sys.exit(1)
    print("Cleaning build folders...")
    clean_before_build()
    print("Installing dependencies...")
    install_dependencies()
    print("Building executable (pyinstaller tofanari.spec --clean)...")
    exe_path = build_exe(version)
    print("Creating portable release package...")
    release_folder = create_release_package(exe_path)
    zip_path = os.path.join(RELEASE_DIR, "TofanariMainTool_portable.zip")
    exe_in_release = os.path.join(release_folder, EXPECTED_EXE)

    # Validate: launch exe briefly to confirm it starts
    print("Verifying EXE launches...")
    try:
        p = subprocess.Popen(
            [exe_in_release],
            cwd=release_folder,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        p.terminate()
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            p.kill()
        print("  EXE launched successfully.")
    except Exception as e:
        print(f"  Warning: Could not verify EXE launch: {e}")

    print("-" * 50)
    print("BUILD COMPLETE")
    print("-" * 50)
    print("VERSION:")
    print(f"  Source: {version} (config.APP_VERSION)")
    print(f"  Verify: Launch EXE and check window title for version.")
    print()
    print("BUILD COMMAND: python build_new_version.py")
    print()
    print("OUTPUT PATHS:")
    print(f"  EXE:            {exe_in_release}")
    print(f"  Release folder: {release_folder}")
    print(f"  Zip archive:    {zip_path}")
    print()
    print("OPERATOR INSTRUCTIONS:")
    print("  - Do NOT copy TofanariMainTool.exe alone. It requires _internal/ and settings/.")
    print("  - Copy the ENTIRE 'TofanariMainTool' folder, or unzip TofanariMainTool_portable.zip.")
    print("  - Run TofanariMainTool.exe from inside that folder.")
    print("  - Optional: Run 'Create_Desktop_Shortcut.bat' to add a desktop shortcut.")


if __name__ == "__main__":
    main()
