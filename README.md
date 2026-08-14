# OOFEM–Salome Plugin

The **OOFEM–Salome Plugin** integrates the open‑source finite element solver **OOFEM** into the **Salome 9.15** platform.  
It provides a GUI‑based workflow for exporting Salome meshes into OOFEM input files and (later) importing OOFEM results back into Salome for visualization.

This plugin is implemented as a **dockable Salome module** with persistent state stored inside the Salome study (element mappings, material assignments, BC mappings, etc.).

---

## ✨ Features

### ✔ Current functionality
- Dockable panel integrated into Salome GUI  
- Mesh selection from active Salome study  
- Editable **element‑type mapping** (Salome → OOFEM)  
- Plugin state stored **inside the Salome study**  
- Basic exporter skeleton (mesh → OOFEM `.in` file)

### 🚧 Planned features
- Material assignment per volume group  
- Boundary condition assignment per face/edge group  
- Full OOFEM input writer  
- OOFEM → MED/VTK postprocessing  
- Multi‑tab GUI (Export / Postprocess)  
- Solver presets and material library

---


---

## 🛠 Installation

The plugin is installed by copying the module directory into Salome’s `modules/` folder.

---

## 🐧 **Installation on Linux**

### 1. Set the Salome installation directory
Example for Salome 9.15:

```sh
export SALOME_ROOT_DIR=/opt/salome-9.15.0
```
### 2. Run the installer
```bash
./install.sh
This copies the plugin into:
```

`$SALOME_ROOT_DIR/modules/OOFEMSalomePlugin/`

### 3. Start Salome
You should see a new menu entry:

`OOFEM → Activate Module`

The dockable panel appears on the left or right side.


## Installation on Windows
### 1. Locate your Salome installation directory
Typically:

`C:\SALOME-9.15.0\`

### 2. Copy the plugin manually
Copy the folder:

`src\OOFEMSalomePlugin\`
into:
`C:\SALOME-9.15.0\W64\KERNEL\lib\python3.9\site-packages\salome`

### 3. Restart Salome
Note: In Salome 9.15 (and 9.16), the SMESH CORBA server is not fully activated until you switch modules. Do this before activating oofem module.

### 4. Activate OOFEM module
In the Salome python console, run:
```python
import importlib
m = importlib.import_module("OOFEMSalomePlugin.OOFEMModule")
mod = m.getModule()
mod.activate()
```



## Usage
* Start Salome
* Activate the OOFEM module from the menu
* The dockable panel appears
* Select a mesh from the study
* Edit element mappings
* Save mappings (stored inside the study)
* Export OOFEM input file (future versions)

## Persistent State
The plugin stores its configuration inside the Salome study using:

`study.SetString()` and `study.GetString()`

The plugin state is serialized to a JSON string and stored directly in the study object.

This means:

* Mappings persist when saving/loading .hdf study files
* Each study can have its own OOFEM configuration
* No external config files required

## Development
Requirements
* Salome 9.15
* Python 3.9 (embedded in Salome)
* PyQt5 (embedded in Salome)

Running inside Salome
Edit files directly under:

## License
GNU LGPL 

## Contributing
Pull requests are welcome.
Please open issues for feature requests or bug reports.

## Contact
OOFEM project: https://oofem.org  
Salome platform: https://www.salome-platform.org