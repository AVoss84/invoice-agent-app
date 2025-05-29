import logging
import os
import inspect
from abc import ABC, abstractmethod
from typing import Literal, Optional, Any
from google.cloud.logging import Client
from google.cloud.logging_v2.handlers import CloudLoggingHandler


class AbstractLoggerFactory(ABC):
    def __init__(
        self,
        handler_type: Literal["File", "Stream", "GCP"] = "Stream",
        filename: Optional[str] = "logger_file.log",
        verbose: bool = False,
    ):
        self.handler_type = handler_type
        self.filename = filename
        self.verbose = verbose

    @abstractmethod
    def create_module_logger(
        self,
        module_name: Optional[str] = None,
        **kwargs: Optional[dict],
    ) -> logging.Logger:
        """
        Creates a logger instance for a specific module.

        Args:
            module_name (str, optional): Name of the module to create logger for. Defaults to None.
            **kwargs: Additional keyword arguments to configure the logger.

        Returns:
            logging.Logger: Logger instance configured for the specified module.

        Raises:
            NotImplementedError: If the subclass does not implement this abstract method.
        """

        raise NotImplementedError(
            "Subclasses must implement create_module_logger method."
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(handler_type={self.handler_type!r}, filename={self.filename!r}, verbose={self.verbose!r})"


class LoggerFactory(AbstractLoggerFactory):
    """
    LoggerFactory is responsible for creating loggers for different modules with various handler types.

    Methods
    -------
    create_module_logger(module_name: Optional[str] = None, **kwargs) -> logging.Logger
        Creates and returns a logger for the specified module with the given handler type.

    Parameters
    ----------
    module_name : Optional[str], optional
        The name of the module for which the logger is being created. Defaults to the current module name.
    **kwargs
        Additional keyword arguments to be passed to the handler.

    Returns
    -------
    logging.Logger
        A configured logger instance for the specified module.
    """

    def __init__(
        self,
        handler_type: Literal["File", "Stream", "GCP"] = "Stream",
        filename: Optional[str] = "logger_file.log",
        verbose: bool = True,
    ):
        super().__init__(handler_type, filename, verbose)

    def create_module_logger(
        self,
        module_name: Optional[str] = None,
        **kwargs: Any,
    ) -> logging.Logger:
        if module_name is None:
            # Dynamically get the name of the calling module
            frame = inspect.stack()[1]
            module = inspect.getmodule(frame[0])
            module_name = module.__name__ if module else "unknown"

        # Create logger
        logger = logging.getLogger(module_name)
        # Remove all existing handlers to avoid duplication
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)

        handler: (
            logging.Handler
        )  # Explicitly declare handler as a generic logging.Handler
        match self.handler_type:
            case "File":
                # Ensure the logging directory exists
                self.log_dir = os.path.join(os.path.dirname(__file__), "logging")
                os.makedirs(self.log_dir, exist_ok=True)

                # Update filename to include the logging directory
                file_path = os.path.join(self.log_dir, self.filename)
                handler = logging.FileHandler(filename=file_path, **kwargs)
            case "Stream":
                handler = logging.StreamHandler()  # default writes to sys.stderr
            case "GCP":
                # integrates with Google Cloud Logging
                try:
                    client = Client()
                    try:
                        handler = CloudLoggingHandler(client, **kwargs)
                    except Exception as e:
                        raise RuntimeError(
                            "Failed to create GCP logging handler. Ensure the 'google-cloud-logging' library is installed and properly configured."
                        ) from e
                except Exception as e:
                    raise RuntimeError("Failed to create GCP logging handler") from e
            case _:
                raise ValueError(f"Invalid handler type: {self.handler_type}")

        # Create formatter and add it to the handler
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Log the created logger and its effective log level
        log_level_name = logging.getLevelName(logger.getEffectiveLevel())
        logger.info(
            f"Logger created for module: {module_name} using log level: {log_level_name}."
        )

        return logger

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(handler_type={self.handler_type!r}, filename={self.filename!r}, verbose={self.verbose!r})"
