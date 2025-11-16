import inspect
import logging
import os
from typing import Literal, Optional

from google.cloud.logging import Client
from google.cloud.logging_v2.handlers import CloudLoggingHandler

# Track configured loggers to avoid duplicate setup
_configured_loggers = set()


class LoggerFactory:
    """
    Singleton factory for creating per-module loggers.

    Usage:
        logger = LoggerFactory.get_instance().create_module_logger()
    """

    _instance: Optional["LoggerFactory"] = None

    def __init__(
        self,
        handler_type: Literal["File", "Stream", "GCP"] = "Stream",
        filename: str = "app.log",
        verbose: bool = True,
    ):
        self.handler_type = handler_type
        self.filename = filename
        self.verbose = verbose

    @classmethod
    def get_instance(cls) -> "LoggerFactory":
        """Get or create the singleton LoggerFactory instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_module_logger(
        self,
        module_name: Optional[str] = None,
        level: Optional[int] = None,
    ) -> logging.Logger:
        """
        Create or retrieve a logger for a specific module.

        Args:
            module_name: Module name. If None, auto-detects from caller.
            level: Logging level override (default: DEBUG if verbose else INFO).

        Returns:
            Configured logger for the module.
        """
        # Auto-detect module name if not provided
        if module_name is None:
            frame = inspect.stack()[1]
            module = inspect.getmodule(frame[0])
            module_name = module.__name__ if module else "unknown"

        logger = logging.getLogger(module_name)

        # Return if already configured
        if module_name in _configured_loggers:
            return logger

        # Set level
        logger.setLevel(level or (logging.DEBUG if self.verbose else logging.INFO))
        logger.propagate = True

        # Add handler only if none exist
        if not logger.handlers:
            handler = self._create_handler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            logger.addHandler(handler)

        _configured_loggers.add(module_name)
        return logger

    def _create_handler(self) -> logging.Handler:
        """Create handler based on handler_type."""
        if self.handler_type == "File":
            log_dir = os.path.join(os.path.dirname(__file__), "logging")
            os.makedirs(log_dir, exist_ok=True)
            return logging.FileHandler(os.path.join(log_dir, self.filename))
        elif self.handler_type == "Stream":
            return logging.StreamHandler()
        elif self.handler_type == "GCP":
            try:
                return CloudLoggingHandler(Client())
            except Exception as e:
                raise RuntimeError(
                    "Failed to create GCP logging handler. "
                    "Ensure google-cloud-logging is installed."
                ) from e
        else:
            raise ValueError(f"Invalid handler type: {self.handler_type}")
