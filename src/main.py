import sys
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow

def run_app():
    """Initializes and runs the Iromo application."""
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    run_app()