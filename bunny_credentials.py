# -*- coding: utf-8 -*-
"""
Bunny.net credential input and storage.
GUI dialog preferred; terminal fallback when GUI unavailable.
Credentials saved to settings/bunny_credentials.json (gitignored).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

from config import BUNNY_BASE_URL, get_settings_dir

SETTINGS_DIR = Path(get_settings_dir())
CREDENTIALS_FILE = SETTINGS_DIR / "bunny_credentials.json"
DEFAULT_STORAGE_HOST = "storage.bunnycdn.com"


def load_credentials() -> Dict[str, str]:
    """Load from settings file. Returns empty dict if missing or invalid."""
    if not CREDENTIALS_FILE.is_file():
        return {}
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: str(v).strip() for k, v in data.items() if isinstance(v, str)}
    except Exception:
        pass
    return {}


def save_credentials(creds: Dict[str, str]) -> bool:
    """Save to settings file."""
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        safe = {k: v for k, v in creds.items() if k in ("storage_zone", "api_key", "pull_zone", "storage_host")}
        CREDENTIALS_FILE.write_text(json.dumps(safe, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def test_connection(creds: Dict[str, str]) -> Tuple[bool, str]:
    """
    Test Bunny Storage API access (list root).
    Returns (success, message).
    """
    zone = (creds.get("storage_zone") or "").strip()
    key = (creds.get("api_key") or "").strip()
    host = (creds.get("storage_host") or DEFAULT_STORAGE_HOST).strip().strip("/")
    if not zone:
        return False, "Storage Zone name is required."
    if not key:
        return False, "API Key (Storage Zone password) is required."

    url = f"https://{host}/{quote(zone, safe='')}/"
    try:
        req = urllib.request.Request(url, method="GET", headers={"AccessKey": key})
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.getcode() in (200, 404):
                return True, "Connection successful."
            return False, f"Unexpected response: HTTP {resp.getcode()}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid API Key or Storage Zone password."
        if e.code == 404:
            return True, "Connection successful (empty zone)."
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)


def _try_gui_available() -> bool:
    """Check if Tkinter can create a window (e.g. DISPLAY on Linux)."""
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
        return True
    except Exception:
        return False


def _show_dialog(prefill: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Tkinter credential dialog. Returns creds dict on Continue, None on Cancel."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    result: Optional[Dict[str, str]] = None
    vars_map: Dict[str, tk.StringVar] = {}

    def get_creds() -> Dict[str, str]:
        return {
            "storage_zone": (vars_map.get("storage_zone") or tk.StringVar()).get().strip(),
            "api_key": (vars_map.get("api_key") or tk.StringVar()).get().strip(),
            "pull_zone": (vars_map.get("pull_zone") or tk.StringVar()).get().strip(),
            "storage_host": (vars_map.get("storage_host") or tk.StringVar()).get().strip() or DEFAULT_STORAGE_HOST,
        }

    def on_test():
        c = get_creds()
        if not c["storage_zone"] or not c["api_key"]:
            messagebox.showwarning("Missing fields", "Storage Zone and API Key are required.")
            return
        ok, msg = test_connection(c)
        if ok:
            messagebox.showinfo("Connection test", f"Success: {msg}")
        else:
            messagebox.showerror("Connection test", msg)

    def on_save():
        c = get_creds()
        if save_credentials(c):
            messagebox.showinfo("Saved", "Credentials saved to settings.")
        else:
            messagebox.showerror("Error", "Could not save credentials.")

    def on_continue():
        nonlocal result
        c = get_creds()
        if not c["storage_zone"] or not c["api_key"]:
            messagebox.showwarning("Missing fields", "Storage Zone and API Key are required to upload.")
            return
        result = c
        root.destroy()

    def on_cancel():
        root.destroy()

    root = tk.Tk()
    root.title("Bunny.net Upload - Credentials")
    root.geometry("520x320")
    root.resizable(True, True)

    main = ttk.Frame(root, padding=16)
    main.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main, text="Enter your Bunny Storage credentials", font=("", 11, "bold")).pack(anchor=tk.W)
    if prefill.get("storage_zone") or prefill.get("api_key"):
        ttk.Label(main, text="(Saved credentials loaded - edit if needed)", font=("", 9), foreground="gray").pack(anchor=tk.W)

    fields = [
        ("Storage Zone name:", "storage_zone", "e.g. my-storage-zone", False),
        ("API Key (Storage password):", "api_key", "From FTP & API Access tab", True),
        ("Pull Zone URL:", "pull_zone", "e.g. https://your-zone.b-cdn.net", False),
        ("Storage host (optional):", "storage_host", f"default: {DEFAULT_STORAGE_HOST}", False),
    ]

    for i, (label, key, hint, is_password) in enumerate(fields):
        ttk.Label(main, text=label).pack(anchor=tk.W, pady=(12 if i else 8, 2))
        v = tk.StringVar(value=prefill.get(key, ""))
        vars_map[key] = v
        e = tk.Entry(main, textvariable=v, width=55, show="*" if is_password else "")
        e.pack(anchor=tk.W, fill=tk.X, pady=(0, 2))
        ttk.Label(main, text=hint, font=("", 8), foreground="gray").pack(anchor=tk.W)
    if not prefill.get("pull_zone"):
        vars_map["pull_zone"].set(BUNNY_BASE_URL)

    btn_frame = ttk.Frame(main)
    btn_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(btn_frame, text="Test connection", command=on_test).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_frame, text="Save credentials", command=on_save).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_frame, text="Continue upload", command=on_continue).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT)

    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()
    return result


def _show_terminal_prompt(prefill: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Terminal credential prompt. Returns creds dict on Continue, None on Cancel."""
    print("\n--- Bunny.net Upload - Credentials ---\n")
    print("Enter credentials (press Enter to use saved value, or 'q' to cancel):\n")

    def prompt(label: str, default: str, secret: bool) -> Optional[str]:
        display = "(saved)" if secret and default else (default or "(none)")
        val = input(f"  {label} [{display}]: ").strip()
        if val.lower() == "q":
            return None
        return val if val else (default or "")

    zone = prompt("Storage Zone name", prefill.get("storage_zone", ""), False)
    if zone is None:
        return None
    key = prompt("API Key (Storage password)", prefill.get("api_key", ""), True)
    if key is None:
        return None
    pull = prompt("Pull Zone URL", prefill.get("pull_zone", "") or BUNNY_BASE_URL, False)
    if pull is None:
        return None
    host = prompt("Storage host (optional)", prefill.get("storage_host", "") or DEFAULT_STORAGE_HOST, False)
    if host is None:
        return None

    return {
        "storage_zone": zone,
        "api_key": key,
        "pull_zone": pull.strip() or BUNNY_BASE_URL,
        "storage_host": host.strip() or DEFAULT_STORAGE_HOST,
    }


def get_credentials_for_upload() -> Optional[Dict[str, str]]:
    """
    Prompt operator for Bunny credentials.
    Uses GUI if available, else terminal.
    Prefills from saved settings when present.
    Returns credentials dict on Continue, None on Cancel.
    """
    prefill = load_credentials()
    if _try_gui_available():
        return _show_dialog(prefill)
    return _show_terminal_prompt(prefill)
