"""Start the backend:  python -m app.backend.api

Loopback only, a single process, no auto-reload: this process is the one owner of the
controller transport (and of the serial port in fpga mode).
"""
import uvicorn

from app.backend.api.app import create_app
from app.backend.runtime.stores import Settings


def main() -> None:
    settings = Settings.from_env()
    if settings.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("API_HOST must stay on loopback (127.0.0.1); this backend controls hardware.")
    app = create_app(settings)
    info = app.state.runtime.transport_info()
    print(f"Interstellar backend  http://{settings.host}:{settings.port}")
    print(f"Controller: {info['controller_label']}   brain enabled: {settings.brain_enabled}")
    print(f"Operator token (header X-Operator-Token): {app.state.operator_token}")
    uvicorn.run(app, host=settings.host, port=settings.port, workers=1, reload=False, log_level="info")


if __name__ == "__main__":
    main()
