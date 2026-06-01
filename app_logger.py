"""Centralized logging for RetinopatiaApp.

Usage in any module:
    import app_logger
    log = app_logger.get(__name__)
    log.info("something happened")
    log.error("something failed", exc_info=True)
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_initialized = False


def setup() -> logging.Logger:
    """Initialize file + console logging. Safe to call multiple times."""
    global _initialized
    root = logging.getLogger("app")
    if _initialized:
        return root

    os.makedirs(_LOGS_DIR, exist_ok=True)

    from datetime import datetime
    log_path = os.path.join(_LOGS_DIR, datetime.now().strftime("app_%Y-%m-%d.log"))

    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s:%(lineno)d — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    _initialized = True
    return root


def get(name: str) -> logging.Logger:
    """Return a child logger under the 'app' namespace."""
    return logging.getLogger(f"app.{name}")


def install_excepthook() -> None:
    """Route all unhandled exceptions to the log file with full traceback."""
    root = logging.getLogger("app")

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        root.critical(
            "Необработанное исключение — приложение завершилось аварийно",
            exc_info=(exc_type, exc_value, exc_tb),
        )

    sys.excepthook = _hook
