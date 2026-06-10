import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class StegoLogger:
    _logger = None

    @staticmethod
    def get() -> logging.Logger:
        if StegoLogger._logger is not None:
            return StegoLogger._logger

        log_dir = Path.home() / ".stegoxpress" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "stegoxpress.log"

        logger = logging.getLogger("stegoxpress")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        StegoLogger._logger = logger
        return logger
