import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Placeholder for config loading, actual import might differ based on execution context
# from ..config import load_config

DEFAULT_LOGGER_NAME = "csv_to_xml_converter"
DEFAULT_LOG_FORMAT = (
    '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'
)


def setup_logger(
    config: dict | None = None,
    logger_name: str = DEFAULT_LOGGER_NAME,
    *,
    force_reconfigure: bool = False,
) -> logging.Logger:
    """Create or update a ``logging.Logger`` instance.

    Parameters
    ----------
    config : dict, optional
        Configuration dictionary that may contain a ``"logging"`` section.
    logger_name : str, optional
        Name of the logger to retrieve or create.
    force_reconfigure : bool, optional
        When ``True`` and the logger already has handlers attached, existing
        handlers are removed before new ones are added. When ``False`` (the
        default) the pre-configured logger is returned as-is.

    Returns
    -------
    logging.Logger
        The configured logger instance.
    """
    logger = logging.getLogger(logger_name)

    log_conf = (config or {}).get("logging", {})
    log_file_path = log_conf.get("log_file", "logs/app.log")
    log_level_str = log_conf.get("log_level", "INFO").upper()
    enable_console = log_conf.get("console", True)
    enable_file = log_conf.get("file", True)

    log_level = getattr(logging, log_level_str, logging.INFO)
    if not isinstance(log_level, int):
        sys.stderr.write(f"Warning: Invalid log level '{log_level_str}'. Defaulting to INFO.\n")
        log_level = logging.INFO

    logger.setLevel(log_level)

    if logger.hasHandlers():
        if force_reconfigure:
            for handler in logger.handlers[:]:
                if hasattr(handler, "close"):
                    try:
                        handler.close()
                    except Exception:
                        pass
                logger.removeHandler(handler)
        else:
            return logger

    try:
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        sys.stderr.write(f"Warning: Could not create log directory {log_dir}: {e}. Using fallback.\n")
        log_file_path = os.path.basename(log_file_path) or "app.log"

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        logger.addHandler(console_handler)

    if enable_file and log_file_path:
        try:
            file_handler = RotatingFileHandler(
                log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            sys.stderr.write(
                f"Error: Could not set up file logging at {log_file_path}: {e}\n"
            )
            logger.error(
                f"Failed to initialize file logger at {log_file_path}", exc_info=False
            )

    logger.info(f"Logger '{logger_name}' initialized. Level: {log_level_str}. Log file: {log_file_path if 'file_handler' in locals() else 'N/A'}")
    return logger


