"""Whether EWOK draws text with the Pillow JAWA's Brander renders with.

Text measurement differs between Pillow releases, and wallrender's shrink,
ellipsis and overflow choices follow it, so a different Pillow can fit a
name that devices cut off.
"""

import PIL

import config


def _major_minor(version):
    return ".".join(str(version).split(".")[:2])


def pillow_check():
    """{ewok, jawa, matches} by major.minor, plus a warning when they differ."""
    ewok, jawa = _major_minor(PIL.__version__), _major_minor(config.PILLOW_TARGET)
    check = {"ewok": ewok, "jawa": jawa, "matches": ewok == jawa}
    if not check["matches"]:
        check["warning"] = f"Preview may differ from devices: EWOK runs Pillow {ewok}, JAWA {jawa}."
    return check
