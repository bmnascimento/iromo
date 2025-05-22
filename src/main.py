import sys
from PyQt6.QtWidgets import QApplication
from .main_window import MainWindow
from .logger_config import setup_logging, APP_NAME
import logging

def run_app():
    """Initializes and runs the Iromo application."""
    setup_logging()
    logger = logging.getLogger(APP_NAME)
    logger.info("Iromo application starting...")
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    exit_code = app.exec()
    logger.info(f"Iromo application finished with exit code {exit_code}.")
    sys.exit(exit_code)

if __name__ == '__main__':
    run_app()