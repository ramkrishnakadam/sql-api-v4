"""Local development entry point for Sql Api V4.

Usage:
    cp .env.example .env
    # fill in DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN
    python run_local.py
"""

import os
import sys


def main() -> None:
    """Start the app locally with reload enabled."""
    token = os.getenv("DATABRICKS_TOKEN")
    host = os.getenv("DATABRICKS_HOST")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")

    if not token:
        print("ERROR: DATABRICKS_TOKEN is required for local development.")
        print("Generate a PAT: Workspace > Settings > Developer > Access tokens")
        sys.exit(1)
    if not host:
        print("ERROR: DATABRICKS_HOST is required.")
        sys.exit(1)
    if not http_path:
        print("ERROR: DATABRICKS_HTTP_PATH is required.")
        sys.exit(1)

    os.environ.setdefault("IDENTITY_MODE", "app")
    os.environ.setdefault("APP_AUTH_MODE", "none")

    print("Starting Sql Api V4 locally on http://localhost:8000 ...")
    print("  Docs: http://localhost:8000/docs")

    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
