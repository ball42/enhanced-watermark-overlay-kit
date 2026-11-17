"""wallrender: render wallpaper templates with device variables.

Shared by EWOK (design and preview) and JAWA Brander (per-device render),
so the preview is exactly what a device receives. See README.md."""

from .render import AssetCache, lint, render, render_with_lint, render_with_report
from .schema import SCHEMA_VERSION, TemplateError, required_version, validate

__all__ = ["AssetCache", "SCHEMA_VERSION", "TemplateError", "lint", "render", "render_with_lint", "render_with_report",
           "required_version", "validate"]
__version__ = "0.14.0"
