import os
import sys
from pathlib import Path

print("=== DEBUG RAILWAY ===")
print(f"Python: {sys.version}")
print(f"Current directory: {Path.cwd()}")
print(f"Files in current dir: {list(Path('.').iterdir())}")

# Vérifiez static
static_path = Path('static')
print(f"Static path: {static_path}")
print(f"Static exists: {static_path.exists()}")

if static_path.exists():
    print("Static content:")
    for item in static_path.rglob('*'):
        print(f"  {item}")
else:
    print("❌ Static directory not found")

print(f"Environment: {os.environ.get('RAILWAY_ENVIRONMENT', 'NOT SET')}")