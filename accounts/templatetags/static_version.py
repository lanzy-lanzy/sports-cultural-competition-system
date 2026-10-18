"""Cache-busting helper for local static assets.

Appends a file's last-modified timestamp as a ``?v=`` query string so that
editing a CSS/JS file changes its URL. The browser then treats it as a new
resource and always fetches the latest version, removing the need for a manual
(hard) refresh after design changes.
"""

from __future__ import annotations

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(path: str) -> str:
    """Return the static URL for ``path`` with a mtime-based cache buster."""
    url = static(path)
    version = _version_for(path)
    return f"{url}?v={version}" if version else url


def _version_for(path: str) -> str:
    source_path = finders.find(path)
    if not source_path:
        return ""
    try:
        return str(int(os.path.getmtime(source_path)))
    except OSError:
        return ""
