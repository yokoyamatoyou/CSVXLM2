import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Placeholder for config loading, actual import might differ based on execution context
# from ..config import load_config

DEFAULT_LOGGER_NAME = "csv_to_xml_converter"
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'

def setup_logger(config: dict = None, logger_name: str = DEFAULT_LOGGER_NAME) -> logging.Logger:
    logger = logging.getLogger(logger_name)

    log_conf = (config or {}).get("logging", {})
    log_file_path = log_conf.get("log_file", "logs/app.log")
    log_level_str = log_conf.get("log_level", "INFO").upper()

    log_level = getattr(logging, log_level_str, logging.INFO)
    if not isinstance(log_level, int):
        sys.stderr.write(f"Warning: Invalid log level '{log_level_str}'. Defaulting to INFO.\n")
        log_level = logging.INFO

    logger.setLevel(log_level)

    if logger.hasHandlers():
        # Assuming already configured, or clear them if re-configuration is desired
        # for handler in logger.handlers[:]: logger.removeHandler(handler)
        return logger

    try:
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        sys.stderr.write(f"Warning: Could not create log directory {log_dir}: {e}. Using fallback.\n")
        log_file_path = os.path.basename(log_file_path) or "app.log"

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    try:
        file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
    except (OSError, IOError) as e:
        sys.stderr.write(f"Error: Could not set up file logging at {log_file_path}: {e}\n")
        # Log to console if file handler failed
        logger.error(f"Failed to initialize file logger at {log_file_path}", exc_info=False)

    logger.info(f"Logger '{logger_name}' initialized. Level: {log_level_str}. Log file: {log_file_path if 'file_handler' in locals() else 'N/A'}")
    return logger

if __name__ == '__main__':
    print("Running logger module self-test (simplified)...")

    # Mock config for basic testing
    mock_config = {
        "logging": {
            "log_file": "logs/test_logger_simplified.log",
            "log_level": "DEBUG"
        }
    }

    # Ensure logs directory exists for the test log file
    test_log_dir = os.path.dirname(mock_config["logging"]["log_file"])
    if not os.path.exists(test_log_dir):
        os.makedirs(test_log_dir, exist_ok=True)

    print(f"--- Test with mock configuration ---")
    test_logger = setup_logger(config=mock_config, logger_name="simplified_test_logger")
    test_logger.debug("This is a DEBUG message.")
    test_logger.info("This is an INFO message.")

    actual_log_file = mock_config["logging"]["log_file"]
    if os.path.exists(actual_log_file):
        print(f"Test log file created: {actual_log_file}")
        # Basic check: read the log file and see if it contains our messages
        try:
            with open(actual_log_file, 'r') as f_log:
                log_content = f_log.read()
                if "DEBUG message" in log_content and "INFO message" in log_content:
                    print("Log content verified.")
                else:
                    print("Error: Log content mismatch or missing.")
        except Exception as e_read:
            print(f"Error reading test log file: {e_read}")

    else:
        print(f"Error: Test log file NOT created at {actual_log_file}")

    print("Logger module self-test (simplified) completed.")
