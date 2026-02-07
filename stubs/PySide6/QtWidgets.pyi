from typing import Any

__all__ = [
    "QWidget",
    "QApplication",
    "QCheckBox",
    "QComboBox",
    "QGridLayout",
    "QGroupBox",
    "QHBoxLayout",
    "QLabel",
    "QLineEdit",
    "QListWidget",
    "QFormLayout",
    "QMessageBox",
    "QFileDialog",
    "QPushButton",
    "QProgressBar",
    "QTabWidget",
    "QTextEdit",
    "QVBoxLayout",
]


class QWidget:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def setLayout(self, layout: Any) -> None: ...

    def setWindowTitle(self, title: str | Any) -> None: ...

    def geometry(self) -> Any: ...

    def frameGeometry(self) -> Any: ...

    def move(self, point: Any) -> None: ...

    def windowState(self) -> Any: ...

    def setGeometry(self, rect: Any) -> None: ...

    def resize(self, width: int, height: int) -> None: ...

    def show(self) -> None: ...

    def changeEvent(self, event: Any) -> None: ...


QApplication: Any
QCheckBox: Any
QComboBox: Any
QGridLayout: Any
QGroupBox: Any
QHBoxLayout: Any
QLabel: Any
QLineEdit: Any
QListWidget: Any
QFormLayout: Any
QMessageBox: Any
QFileDialog: Any
QPushButton: Any
QProgressBar: Any
QTabWidget: Any
QTextEdit: Any
QVBoxLayout: Any