# src/OOFEMSalomePlugin/OOFEMDebugConsole.py
from PyQt5 import QtWidgets

class DebugConsole(QtWidgets.QDockWidget):
    def __init__(self, parent=None, logLevel=0):
        super().__init__("OOFEM Debug Console", parent)

        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.setWidget(self.text)
        self.logLevel = logLevel


    def log(self, msg, level=0):
        if level <= self.logLevel:
            self.text.append(str(msg))
            QtWidgets.QApplication.processEvents()  # force immediate refresh