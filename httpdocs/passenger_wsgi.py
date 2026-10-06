import importlib.util
import os
import sys

# Ein Ordner höher zum eigentlichen Projektstammverzeichnis
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

parent_wsgi_path = os.path.join(PARENT_DIR, "passenger_wsgi.py")

if os.path.exists(parent_wsgi_path):
    spec = importlib.util.spec_from_file_location("root_passenger_wsgi", parent_wsgi_path)
    root_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root_module)
    application = root_module.application
else:
    # Direkter Fallback falls doch im gleichen Verzeichnis ausgeführt
    from a2wsgi import ASGIMiddleware
    from app.main import app
    application = ASGIMiddleware(app)
