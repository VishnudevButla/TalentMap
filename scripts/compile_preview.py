#!/usr/bin/env python
import os
import sys
import time
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Set up paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.services.dashboard_data import get_sample_dashboard_context
except ImportError:
    # Fallback to empty dict if app structure is not fully importable
    def get_sample_dashboard_context(user_id):
        return {}

TEMPLATES_DIR = PROJECT_ROOT / "templates"
PREVIEW_DIR = PROJECT_ROOT / "preview"
STATIC_DIR = PROJECT_ROOT / "static"

# Ensure preview directories exist
PREVIEW_DIR.mkdir(exist_ok=True)
(PREVIEW_DIR / "auth").mkdir(exist_ok=True)

# Templates to compile and their target outputs
TEMPLATES_TO_COMPILE = [
    {
        "template_name": "auth/login.html",
        "output_path": PREVIEW_DIR / "auth/login.html",
        "depth": 1,
        "context": {}
    },
    {
        "template_name": "auth/register.html",
        "output_path": PREVIEW_DIR / "auth/register.html",
        "depth": 1,
        "context": {}
    },
    {
        "template_name": "dashboard.html",
        "output_path": PREVIEW_DIR / "dashboard.html",
        "depth": 0,
        "context": get_sample_dashboard_context("demo")
    },
    {
        "template_name": "upload.html",
        "output_path": PREVIEW_DIR / "upload.html",
        "depth": 0,
        "context": {}
    }
]

def get_relative_root(depth):
    return "../" * (depth + 1)

def compile_templates():
    print("Compiling templates...")
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    
    for item in TEMPLATES_TO_COMPILE:
        template_name = item["template_name"]
        output_path = item["output_path"]
        depth = item["depth"]
        context = item["context"].copy()
        
        # Calculate relative path to project root
        relative_root = get_relative_root(depth)
        
        # Mock url_for function
        def mock_url_for(endpoint, **kwargs):
            if endpoint == 'static':
                path = kwargs.get('path', '')
                return f"{relative_root}static/{path}"
            return "#"
        
        # Inject standard helpers
        context["url_for"] = mock_url_for
        context["request"] = None  # Mock FastAPI request object
        
        try:
            # Render template
            template = env.get_template(template_name)
            rendered_html = template.render(context)
            
            # Post-process: Rewrite page links to static HTML equivalents
            # For auth subfolder (depth = 1):
            # /login -> login.html
            # /register -> register.html
            # /dashboard -> ../dashboard.html
            # /new-analysis -> ../upload.html
            # For root folder (depth = 0):
            # /login -> auth/login.html
            # /register -> auth/register.html
            # /dashboard -> dashboard.html
            # /new-analysis -> upload.html
            
            if depth == 1:
                replacements = {
                    'href="/dashboard"': 'href="../dashboard.html"',
                    'href="/new-analysis"': 'href="../upload.html"',
                    'href="/login"': 'href="login.html"',
                    'href="/register"': 'href="register.html"',
                    'action="/api/login"': 'action="#"',
                    'action="/api/register"': 'action="#"'
                }
            else:
                replacements = {
                    'href="/dashboard"': 'href="dashboard.html"',
                    'href="/new-analysis"': 'href="upload.html"',
                    'href="/login"': 'href="auth/login.html"',
                    'href="/register"': 'href="auth/register.html"',
                    'action="/api/login"': 'action="#"',
                    'action="/api/register"': 'action="#"'
                }
                
            for search_str, replace_str in replacements.items():
                rendered_html = rendered_html.replace(search_str, replace_str)
                
            # Write to output file
            output_path.write_text(rendered_html, encoding="utf-8")
            print(f"  Compiled: {template_name} -> {output_path.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            print(f"  Error compiling {template_name}: {e}")

def get_mtimes():
    """Get max modification times of templates and static folders to watch changes."""
    mtimes = []
    # Watch templates directory
    for root, _, files in os.walk(str(TEMPLATES_DIR)):
        for f in files:
            mtimes.append(os.path.getmtime(os.path.join(root, f)))
    # Watch static directory
    for root, _, files in os.walk(str(STATIC_DIR)):
        for f in files:
            mtimes.append(os.path.getmtime(os.path.join(root, f)))
    return max(mtimes) if mtimes else 0

if __name__ == "__main__":
    compile_templates()
    
    if "--watch" in sys.argv:
        print("\nWatching templates and static files for changes... Press Ctrl+C to stop.")
        try:
            last_mtime = get_mtimes()
            while True:
                time.sleep(1)
                current_mtime = get_mtimes()
                if current_mtime > last_mtime:
                    print("\nChange detected! Recompiling...")
                    compile_templates()
                    last_mtime = current_mtime
        except KeyboardInterrupt:
            print("\nStopped watch mode.")
