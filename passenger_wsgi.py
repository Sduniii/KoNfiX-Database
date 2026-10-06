"""
Phusion Passenger WSGI entry point for Netcup Webhosting (Plesk).
Adapts the ASGI FastAPI application to WSGI via a2wsgi.
"""
import glob
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Virtualenv / site-packages automatisch finden und einbinden
possible_site_packages = [
    os.path.join(PROJECT_DIR, "site-packages"),
    *glob.glob(os.path.join(PROJECT_DIR, "venv", "lib*", "python*", "site-packages")),
    *glob.glob(os.path.join(PROJECT_DIR, ".venv", "lib*", "python*", "site-packages")),
]
for p in possible_site_packages:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from a2wsgi import ASGIMiddleware
from app.main import app

# Passenger looks for 'application' callable by default
application = ASGIMiddleware(app)
