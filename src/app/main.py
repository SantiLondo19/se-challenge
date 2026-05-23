"""ASGI entrypoint. Uvicorn target: `app.main:app`."""
from __future__ import annotations

from app.factory import create_app

app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import os

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=os.environ.get("ENV", "development") == "development",
    )
