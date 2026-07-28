# src/OOFEMSalomePlugin/OOFEMDockWidget.py

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from OOFEMSalomePlugin.OOFEMMainWidget import OOFEMMainWidget

class OOFEMDockWidget(QtWidgets.QDockWidget):
    def __init__(self):
        super().__init__("OOFEM Plugin")
        self.setAllowedAreas(Qt.LeftDockWidgetArea |
                             Qt.RightDockWidgetArea)

        self.mainWidget = OOFEMMainWidget()
        self.setWidget(self.mainWidget)
