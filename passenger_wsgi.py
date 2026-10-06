"""
Phusion Passenger WSGI entry point for Netcup Webhosting (Plesk).
Adapts the ASGI FastAPI application to WSGI via a2wsgi.
"""
import os
import sys

# Ensure project root is in Python sys.path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from a2wsgi import ASGIMiddleware
from app.main import app

# Passenger looks for 'application' callable by default
application = ASGIMiddleware(app)
