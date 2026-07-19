"""app/core/templates.py — single shared Jinja2Templates instance.

Every router that renders HTML imports `templates` from here instead of
constructing its own, so template lookup paths and future globals/filters
stay in one place.
"""

from pathlib import Path
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))