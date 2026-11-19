"""Where the template asset library lives.

It is the only copy of every logo and background, so it stays outside the
checkout: a `git clean -X`, a fresh clone or a moved checkout must not take
it. EWOK_ASSETS_DIR puts it somewhere else.
"""

import os
import shutil
import sys


def default_assets_folder(environ=None, home=None, platform=None):
    """The library folder: EWOK_ASSETS_DIR, else the platform's per-user data folder."""
    environ = os.environ if environ is None else environ
    platform = platform or sys.platform
    override = environ.get("EWOK_ASSETS_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    home = home or os.path.expanduser("~")
    if platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    elif platform.startswith("win"):
        base = environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    else:
        base = environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    return os.path.join(base, "EWOK", "template_assets")


def _has_files(folder):
    return os.path.isdir(folder) and any(os.scandir(folder))


def move_legacy_library(legacy, new):
    """Move a library from inside the checkout (legacy) to its new folder.

    Returns the line to print, or None when there is nothing to say. A
    library already at the new folder is never overwritten or merged into.
    """
    if not os.path.isdir(legacy) or os.path.realpath(legacy) == os.path.realpath(new):
        return None
    if _has_files(new):
        return (f"Warning: EWOK uses the asset library at {new}. An older one is still at "
                f"{legacy}: copy what you need from it, then remove it.")
    if os.path.isdir(new):
        os.rmdir(new)  # empty, so nothing is lost
    os.makedirs(os.path.dirname(new), exist_ok=True)
    shutil.move(legacy, new)
    return f"EWOK moved your asset library from {legacy} to {new}."
