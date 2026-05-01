"""
WSGI entrypoint for containers (gunicorn) and platforms like Cloud Run.

This module must live at the repository root so tools can import `app:app`.
"""

import os

from src.app import create_app

app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)

