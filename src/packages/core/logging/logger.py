import logging
from logging.handlers import RotatingFileHandler
from typing import Any

from packages.core.config import settings


class Logger:
    def __init__(self) -> None:
        self.logger = self.__prepare()

    def debug(self, msg: object, *args: object, **kwargs: Any) -> None:
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: object, *args: object, **kwargs: Any) -> None:
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: object, *args: object, **kwargs: Any) -> None:
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: object, *args: object, **kwargs: Any) -> None:
        self.logger.error(msg, *args, **kwargs)

    def exception(self, msg: object, *args: object, **kwargs: Any) -> None:
        self.logger.exception(msg, *args, **kwargs)

    def fatal(self, msg: object, *args: object, **kwargs: Any) -> None:
        self.logger.fatal(msg, *args, **kwargs)

    def __prepare(self) -> logging.Logger:
        logger = logging.getLogger(settings.app_env)

        if logger.handlers:
            return logger

        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

        # Standard output
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        # Log file (Rotation)
        file_handler = RotatingFileHandler(
            "log/app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)

        logger.propagate = False

        return logger


logger = Logger()
