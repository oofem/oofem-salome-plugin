# OOFEMSalomePlugin package initializer
# - makes development install easier by allowing an env var to point to your repo src
# - tries several import strategies so Salome can find the module reliably
# - exposes getModule() if the real module provides it

import sys
import os
import importlib
import traceback

# 1) Developer override: set this environment variable to the absolute path of your repo's "src" directory
#    Example: setx OOFEM_SALOME_PLUGIN_PATH "C:\Users\you\projects\oofem-salome-plugin\src"
_dev_path = os.environ.get("OOFEM_SALOME_PLUGIN_PATH") or os.environ.get("OOFEM_SALOME_PLUGIN_DEV")
if _dev_path:
    _dev_path = os.path.abspath(_dev_path)
    if os.path.isdir(_dev_path) and _dev_path not in sys.path:
        sys.path.insert(0, _dev_path)

# 2) If package is installed directly in a site-packages or under W64, normal relative import should work
_module = None
try:
    from . import OOFEMModule as _module  # prefer relative import when package is installed as a package
except Exception:
    # 3) Try absolute import in case this __init__ is a lightweight wrapper under W64
    try:
        _module = importlib.import_module("OOFEMSalomePlugin.OOFEMModule")
    except Exception:
        # 4) Try common development layout: look for a sibling or parent 'src' directory and add it to sys.path
        try:
            _here = os.path.dirname(__file__)
            # check a few likely relative locations for a development 'src' folder
            _candidates = [
                os.path.abspath(os.path.join(_here, "..", "src")),
                os.path.abspath(os.path.join(_here, "..", "..", "src")),
                os.path.abspath(os.path.join(_here, "..", "..", "..", "src")),
            ]
            for _cand in _candidates:
                if os.path.isdir(_cand) and _cand not in sys.path:
                    sys.path.insert(0, _cand)
                    try:
                        _module = importlib.import_module("OOFEMSalomePlugin.OOFEMModule")
                        break
                    except Exception:
                        # continue trying other candidates
                        _module = None
        except Exception:
            _module = None

# 5) Expose getModule if available, otherwise provide a helpful ImportError when called
if _module is not None and hasattr(_module, "getModule"):
    getModule = _module.getModule
else:
    def getModule():
        # Provide a clear runtime error with guidance for debugging
        msg = (
            "OOFEMSalomePlugin.getModule: failed to import OOFEMModule.\n"
            "Possible fixes:\n"
            " - Copy the package into Salome's site-packages, for example:\n"
            "   C:\\SALOME-9.15.0\\W64\\KERNEL\\lib\\python3.9\\site-packages\\OOFEMSalomePlugin\n"
            " - Create a .pth file in a site-packages pointing to your repo's src directory\n"
            " - Set environment variable OOFEM_SALOME_PLUGIN_PATH to your repo's src directory\n"
            " - Use a wrapper package under W64 that inserts your src into sys.path\n"
            "Check Salome Python console for the original import traceback."
        )
        # Print traceback to Salome console for diagnostics
        try:
            raise ImportError(msg)
        except ImportError:
            traceback.print_exc()
            raise

# 6) Optional: attempt to import on package load to surface errors early
#    Comment out the block below if you prefer lazy import
try:
    if _module is None:
        # attempt one last time using importlib to capture a traceback
        _module = importlib.import_module("OOFEMSalomePlugin.OOFEMModule")
        if hasattr(_module, "getModule"):
            getModule = _module.getModule
except Exception:
    # swallow here to avoid breaking Salome startup, but print traceback for debugging
    traceback.print_exc()
