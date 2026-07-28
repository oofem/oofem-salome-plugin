# src/OOFEMSalomePlugin/OOFEMModule.py

import salome
import traceback
from PyQt5 import QtWidgets, QtCore
import logging
from OOFEMSalomePlugin.OOFEMDockWidget import OOFEMDockWidget
from OOFEMSalomePlugin.OOFEMDebugConsole import DebugConsole


# Global instance to hold a reference to the module, preventing it from being
# garbage collected when activated from the Python console.
_oofem_module_instance = None
 
_logger = logging.getLogger("OOFEMSalomePlugin")

def salome_warn(msg):
    # Try known salome GUI helpers, fall back to logger/print
    try:
        if hasattr(salome, "sg") and hasattr(salome.sg, "warning"):
            salome.sg.warning(msg)
            return
        if hasattr(salome, "sg") and hasattr(salome.sg, "showMessage"):
            # some builds expose showMessage or showInfo
            salome.sg.showMessage(msg)
            return
    except Exception:
        # swallow GUI errors and continue to fallback
        pass

    # fallback: log and print the message and traceback
    _logger.warning(msg)
    print(msg)
    traceback.print_exc()


class OOFEMModule:
    def __init__(self):
        self.dock = None
        self.debug_console = None
        print("OOFEMModule instance created.")

    def activate(self):
        try:
            # Find main window first, it's needed for both widgets
            main_window = None
            for widget in QtWidgets.QApplication.topLevelWidgets():
                if isinstance(widget, QtWidgets.QMainWindow):
                    main_window = widget
                    break

            if not main_window:
                salome_warn("OOFEM Plugin Error: Could not find Salome's main window.")
                return

            if not self.dock:
                print("Creating OOFEMDockWidget...")
                self.dock = OOFEMDockWidget()
                # The 'salome.sg.addDockWidget' method is not available in all versions.
                # The robust way is to find the application's QMainWindow and add the dock widget to it.
                main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dock)
                print("OOFEMDockWidget added to Salome GUI.")

            if not self.debug_console:
                print("Creating OOFEM Debug Console...")
                self.debug_console = DebugConsole(main_window)
                main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.debug_console)

            self.dock.show()
            self.debug_console.show()
        except Exception as e:
            print("ERROR: Failed to activate OOFEM module.")
            traceback.print_exc()
            salome_warn("OOFEM Plugin failed to load. See console for details.")

def getModule():
    """
    Returns a singleton instance of the OOFEMModule.
    This is crucial to prevent the module from being garbage collected.
    """
    global _oofem_module_instance
    if _oofem_module_instance is None:
        _oofem_module_instance = OOFEMModule()
    return _oofem_module_instance
