"""Script to generate docs."""

import json
import subprocess
from pathlib import Path

from app.main import app

# Make docs directory if it doesn't exist
docs_path = Path("docs")
docs_path.mkdir(exist_ok=True)

# Dump OpenAPI spec
with open(docs_path / "openapi.json", "w") as f:
    json.dump(app.openapi(), f, indent=2)

# Generate static HTML with ReDoc
subprocess.run(
    [
        "npx",
        "redoc-cli",
        "build",
        str(docs_path / "openapi.json"),
        "-o",
        str(docs_path / "index.html"),
    ],
    check=True,
)
