import logging
import logging.handlers
import os
import platform
from pathlib import Path

APP_NAME = "iromo"
LOG_FILE_NAME = f"{APP_NAME}_app.log"
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

def get_log_file_path() -> Path:
    """Determines the appropriate platform-specific path for the log file."""
    system = platform.system()
    if system == "Windows":
        log_dir = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME / "logs"
    elif system == "Darwin":  # macOS
        log_dir = Path.home() / "Library" / "Application Support" / APP_NAME / "logs"
    else:  # Linux and other Unix-like systems
        log_dir = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / LOG_FILE_NAME

def setup_logging():
    """Configures the application-wide logger."""
    # Get the root logger so all module loggers inherit this configuration
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Set root logger level to DEBUG

    # Prevent multiple handlers if setup_logging is called more than once (e.g., in tests)
    if logger.hasHandlers():
        logger.handlers.clear()

    log_file_path = get_log_file_path()

    # Rotating File Handler
    rfh = logging.handlers.RotatingFileHandler(
        filename=log_file_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'
    )
    rfh.setFormatter(formatter)
    logger.addHandler(rfh)

    # Optional: Console Handler for development/debugging
    # To enable, uncomment the following lines.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG) # Changed to DEBUG to capture all messages
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized. Log file: {log_file_path}. Console output enabled. Log level: DEBUG")

if __name__ == '__main__':
    # Example usage:
    setup_logging()
    test_logger = logging.getLogger(APP_NAME) # Get the same app logger
    test_logger.debug("This is a debug message.") # Won't show if level is INFO
    test_logger.info("This is an info message.")
    test_logger.warning("This is a warning message.")
    test_logger.error("This is an error message.")
    test_logger.critical("This is a critical message.")
    print(f"Check log file at: {get_log_file_path()}")