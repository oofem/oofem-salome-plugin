# src/OOFEMSalomePlugin/OOFEMMainWidget.py

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
import json
import os
import uuid
import traceback

from OOFEMSalomePlugin.OOFEMState import OOFEMState
from OOFEMSalomePlugin.OOFEMMapping import DEFAULT_ELEMENT_MAP
from OOFEMSalomePlugin.OOFEMMaterialDialog import OOFEMMaterialDialog
from OOFEMSalomePlugin.OOFEMBCDialog import OOFEMBCDialog


class OOFEMMainWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Defer study and state loading until populateAll() is called.
        self.study = None
        self.state = {}
        self.material_templates = []
        self.analysis_templates = []
        self.bc_templates = []
        self._block_signals = False

        layout = QtWidgets.QVBoxLayout()

        # --- Top-level controls ---
        top_layout = QtWidgets.QHBoxLayout()
        self.refreshBtn = QtWidgets.QPushButton("🔄 Load/Refresh Data from Study")
        self.refreshBtn.clicked.connect(self.populateAll)
        top_layout.addWidget(self.refreshBtn)
        layout.addLayout(top_layout)

        # Mesh selector
        layout.addWidget(QtWidgets.QLabel("Select Mesh:"))
        self.meshCombo = QtWidgets.QComboBox()
        layout.addWidget(self.meshCombo)

        # --- Tabbed interface for different settings ---
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: Analysis
        analysis_tab = QtWidgets.QWidget()
        analysis_layout = QtWidgets.QVBoxLayout(analysis_tab)
        analysis_form_layout = QtWidgets.QFormLayout()
        self.analysisTypeCombo = QtWidgets.QComboBox()
        self.analysisTypeCombo.currentIndexChanged.connect(self.onAnalysisTypeChanged)
        analysis_form_layout.addRow("Analysis Type:", self.analysisTypeCombo)
        analysis_layout.addLayout(analysis_form_layout)

        analysis_props_group = QtWidgets.QGroupBox("Analysis Parameters")
        analysis_props_layout = QtWidgets.QVBoxLayout(analysis_props_group)
        self.analysisPropsTable = QtWidgets.QTableWidget()
        self.analysisPropsTable.setColumnCount(2)
        self.analysisPropsTable.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.analysisPropsTable.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.analysisPropsTable.cellChanged.connect(self.onAnalysisPropertyChanged)
        analysis_props_layout.addWidget(self.analysisPropsTable)
        analysis_layout.addWidget(analysis_props_group)
        analysis_layout.addStretch()
        self.tabs.addTab(analysis_tab, "Analysis")

        # Tab 2: Element Mapping
        elem_tab = QtWidgets.QWidget()
        elem_layout = QtWidgets.QVBoxLayout(elem_tab)
        self.elemTable = QtWidgets.QTableWidget()
        self.elemTable.setColumnCount(2)
        self.elemTable.setHorizontalHeaderLabels(["Salome Type", "OOFEM Type"])
        elem_layout.addWidget(self.elemTable)
        self.tabs.addTab(elem_tab, "Element Mapping")

        # Tab 3: Materials
        mat_tab = QtWidgets.QWidget()
        mat_layout = QtWidgets.QVBoxLayout(mat_tab)
        
        # Buttons for adding/removing materials
        mat_btn_layout = QtWidgets.QHBoxLayout()
        self.addMatBtn = QtWidgets.QPushButton("Add Material")
        self.addMatBtn.clicked.connect(self.addMaterial)
        self.removeMatBtn = QtWidgets.QPushButton("Remove Material")
        self.removeMatBtn.clicked.connect(self.removeMaterial)
        mat_btn_layout.addWidget(self.addMatBtn)
        mat_btn_layout.addWidget(self.removeMatBtn)
        mat_layout.addLayout(mat_btn_layout)

        # Table of defined materials
        self.matTable = QtWidgets.QTableWidget()
        self.matTable.setColumnCount(3)
        self.matTable.setHorizontalHeaderLabels(["Name", "OOFEM Type", "Assigned Group"])
        self.matTable.itemSelectionChanged.connect(self.populateMaterialDetails)
        self.matTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.matTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        mat_layout.addWidget(self.matTable)
        
        # --- Material Properties Editor ---
        props_group = QtWidgets.QGroupBox("Material Properties (select a material above)")
        props_layout = QtWidgets.QVBoxLayout(props_group)
        self.matPropsTable = QtWidgets.QTableWidget()
        self.matPropsTable.setColumnCount(2)
        self.matPropsTable.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.matPropsTable.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.matPropsTable.cellChanged.connect(self.onMaterialPropertyChanged)
        props_layout.addWidget(self.matPropsTable)
        mat_layout.addWidget(props_group)

        # Spacer
        mat_layout.addStretch()
        self.tabs.addTab(mat_tab, "Materials")

        # Tab 4: Boundary Conditions
        bc_tab = QtWidgets.QWidget()
        bc_layout = QtWidgets.QVBoxLayout(bc_tab)

        bc_btn_layout = QtWidgets.QHBoxLayout()
        self.addBCBtn = QtWidgets.QPushButton("Add Boundary Condition")
        self.addBCBtn.clicked.connect(self.addBC)
        self.removeBCBtn = QtWidgets.QPushButton("Remove Boundary Condition")
        self.removeBCBtn.clicked.connect(self.removeBC)
        bc_btn_layout.addWidget(self.addBCBtn)
        bc_btn_layout.addWidget(self.removeBCBtn)
        bc_layout.addLayout(bc_btn_layout)

        self.bcTable = QtWidgets.QTableWidget()
        self.bcTable.setColumnCount(3)
        self.bcTable.setHorizontalHeaderLabels(["Name", "OOFEM Type", "Assigned Group"])
        self.bcTable.itemSelectionChanged.connect(self.populateBCDetails)
        self.bcTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.bcTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        bc_layout.addWidget(self.bcTable)

        bc_props_group = QtWidgets.QGroupBox("BC Properties (select a BC above)")
        bc_props_layout = QtWidgets.QVBoxLayout(bc_props_group)
        self.bcPropsTable = QtWidgets.QTableWidget()
        self.bcPropsTable.setColumnCount(2)
        self.bcPropsTable.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.bcPropsTable.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.bcPropsTable.cellChanged.connect(self.onBCPropertyChanged)
        bc_props_layout.addWidget(self.bcPropsTable)
        bc_layout.addWidget(bc_props_group)

        bc_layout.addStretch()
        self.tabs.addTab(bc_tab, "Boundary Conditions")


        # --- Bottom buttons ---
        bottom_layout = QtWidgets.QHBoxLayout()
        self.saveBtn = QtWidgets.QPushButton("💾 Save All to Study")
        self.saveBtn.clicked.connect(self.saveState)
        bottom_layout.addWidget(self.saveBtn)

        # Export button
        self.exportBtn = QtWidgets.QPushButton("🚀 Generate OOFEM Input")
        self.exportBtn.clicked.connect(self.export)
        bottom_layout.addWidget(self.exportBtn)
        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    def loadAnalysisTemplates(self):
        """Loads analysis definitions from the JSON file."""
        try:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(plugin_dir, "OOFEMAnalyses.json")
            with open(json_path, 'r') as f:
                data = json.load(f)
                self.analysis_templates = data.get("analyses", [])
        except Exception as e:
            print(f"Error loading analysis templates: {e}")
            self.analysis_templates = []

    def loadMaterialTemplates(self):
        """Loads material definitions from the JSON file."""
        try:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(plugin_dir, "OOFEMMaterials.json")
            with open(json_path, 'r') as f:
                data = json.load(f)
                self.material_templates = data.get("materials", [])
        except Exception as e:
            print(f"Error loading material templates: {e}")
            self.material_templates = []

    def loadBCTemplates(self):
        """Loads boundary condition definitions from the JSON file."""
        try:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(plugin_dir, "OOFEMBCs.json")
            with open(json_path, 'r') as f:
                data = json.load(f)
                self.bc_templates = data.get("boundary_conditions", [])
        except Exception as e:
            print(f"Error loading BC templates: {e}")
            self.bc_templates = []
    def populateAll(self):
        # Load state and populate UI. Called from the refresh button.

        # Your suggestion to call salome.salome_init() is correct. This function is
        # needed to establish the connection between the Python script and the running
        # Salome application core. This patch cleans up all previous attempts and
        # implements this correct initialization sequence.
        current_study = None
        try:
            import salome
            salome.salome_init()
            current_study = salome.myStudy
        except Exception as e:
            # This will fail if no study is active or if the connection fails.
            pass

        if not current_study:
            QtWidgets.QMessageBox.warning(self, "Study Not Found",
                                          "Could not find an active study.\n\n"
                                          "Please open or create a study before refreshing the plugin.")
            return

        # Check if the SMESH component is active.
        smesh_comp = current_study.FindComponent("SMESH")
        if not smesh_comp:
            # Automatic activation can cause crashes in Salome 9.15.
            # We will just check for the module and ask the user to activate it if missing.
            comp_user_name = "Mesh" # Default user-facing name
            try:
                # getComponentUserName provides the localized name (e.g., "Maillage" in French)
                comp_user_name = salome.sg.getComponentUserName("SMESH")
            except Exception:
                pass # Use default name on failure

            # Inform the user that the module needs to be activated manually.
            QtWidgets.QMessageBox.warning(self, f"{comp_user_name} Module Not Active",
                                          f"The {comp_user_name} module is not active.\n\n"
                                          f"Please activate the '{comp_user_name}' module manually from the dropdown menu, then click Refresh.")
            return

        # Now that we know the study and SMESH component are valid, assign it to the instance
        self.study = current_study
        self.state = OOFEMState.load(self.study)
        if "element_mapping" not in self.state:
            self.state["element_mapping"] = DEFAULT_ELEMENT_MAP.copy()
        if "materials" not in self.state:
            self.state["materials"] = []
        if "analysis" not in self.state:
            # Set a default analysis if none is defined
            self.state["analysis"] = {
                "oofem_type": "StaticStructural",
                "params": {"nsteps": 1}
            }
        if "bcs" not in self.state:
            self.state["bcs"] = []

        self.loadAnalysisTemplates()
        self.loadMaterialTemplates()
        self.loadBCTemplates()
        self.populateMeshes()
        self.populateAnalysis()
        self.populateElementMapping()
        self.populateMaterials()
        self.populateBCs()

    # ---------------------------
    # Mesh selector
    # ---------------------------
    def populateMeshes(self):
        import salome

        # Clear the combo box before populating with new items.
        self.meshCombo.clear()

        # The SMESH component is guaranteed to exist by the check in populateAll().
        smesh_comp = salome.myStudy.FindComponent("SMESH")

        # Iterate through all objects in the SMESH component, which are the meshes.
        child_iterator = self.study.NewChildIterator(smesh_comp)
        while child_iterator.More():
            s_object = child_iterator.Value()
            mesh_object = s_object.GetObject() # Get the underlying CORBA object
            if mesh_object:
                # Store the SObject's Entry ID. This is a robust, unique identifier
                # that we can use to retrieve the full mesh object later.
                self.meshCombo.addItem(s_object.GetName(), s_object.GetID())
            child_iterator.Next()

    def getMeshGroups(self):
        """Returns a list of mesh group names from the selected mesh."""
        import salome

        mesh_id = self.meshCombo.currentData()
        if not mesh_id:
            return []
        
        try:
            # Get the SMESH component from the study.
            mesh = salome.IDToObject(mesh_id)
            if not mesh:
                print("Could not convert selected object to a mesh.")
                return []
            # GetGroups() returns both node and element groups. We can filter later if needed.
            return [g.GetName() for g in mesh.GetGroups()]
        except Exception as e:
            print(f"Could not get mesh groups: {e}")
            return []

    # ---------------------------
    # Element mapping table
    # ---------------------------
    def populateElementMapping(self):
        mapping = self.state.get("element_mapping", {})
        self.elemTable.setRowCount(0)

        for salome_type, oofem_type in mapping.items():
            row = self.elemTable.rowCount()
            self.elemTable.insertRow(row)
            self.elemTable.setItem(row, 0, QtWidgets.QTableWidgetItem(salome_type))
            self.elemTable.setItem(row, 1, QtWidgets.QTableWidgetItem(oofem_type))
            
    # ---------------------------
    # Analysis
    # ---------------------------
    def populateAnalysis(self):
        """Populates the analysis selection UI."""
        self._block_signals = True
        self.analysisTypeCombo.clear()
        self.analysisTypeCombo.addItems([t['display_name'] for t in self.analysis_templates])

        current_type = self.state.get("analysis", {}).get("oofem_type")
        if current_type:
            idx = next((i for i, t in enumerate(self.analysis_templates) if t['oofem_name'] == current_type), -1)
            if idx != -1:
                self.analysisTypeCombo.setCurrentIndex(idx)
        
        self._block_signals = False
        self.populateAnalysisDetails()

    def populateAnalysisDetails(self):
        """Populates the property editor for the selected analysis."""
        self._block_signals = True
        self.analysisPropsTable.setRowCount(0)

        selected_index = self.analysisTypeCombo.currentIndex()
        if selected_index < 0 or not self.analysis_templates:
            self._block_signals = False
            return

        template = self.analysis_templates[selected_index]
        analysis_data = self.state.get("analysis", {})
        current_params = analysis_data.get("params", {})

        for param_def in template.get("params", []):
            row = self.analysisPropsTable.rowCount()
            self.analysisPropsTable.insertRow(row)
            
            is_optional = param_def.get("optional", False)
            display_name = param_def['name']
            if is_optional:
                display_name += " (optional)"

            name_item = QtWidgets.QTableWidgetItem(display_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setData(Qt.UserRole, param_def['key'])
            name_item.setData(Qt.UserRole + 1, param_def.get('type', 'string'))
            name_item.setData(Qt.UserRole + 2, is_optional)
            
            value = current_params.get(param_def['key'], param_def.get('default', ''))
            value_item = QtWidgets.QTableWidgetItem(str(value))

            description = param_def.get("description")
            if description:
                name_item.setToolTip(description)
                value_item.setToolTip(description)

            self.analysisPropsTable.setItem(row, 0, name_item)
            self.analysisPropsTable.setItem(row, 1, value_item)
        
        self._block_signals = False

    def onAnalysisTypeChanged(self, index):
        """Updates state when a new analysis type is selected."""
        if self._block_signals or index < 0:
            return

        template = self.analysis_templates[index]
        new_type = template['oofem_name']
        
        # Create new params dict with defaults from template
        new_params = {}
        for p in template.get('params', []):
            if 'default' in p:
                new_params[p['key']] = p['default']

        self.state['analysis'] = {
            'oofem_type': new_type,
            'params': new_params
        }
        
        self.populateAnalysisDetails()
            
    # ---------------------------
    # Materials
    # ---------------------------
    def populateMaterials(self):
        """Populates the main material table from the plugin state."""
        self._block_signals = True
        self.matTable.setRowCount(0)
        for i, mat_data in enumerate(self.state.get("materials", [])):
            row = self.matTable.rowCount()
            self.matTable.insertRow(row)
            
            name_item = QtWidgets.QTableWidgetItem(mat_data.get("name", "Unnamed"))
            # Store the material's unique ID in the item for later retrieval
            name_item.setData(Qt.UserRole, mat_data.get("id"))
            
            self.matTable.setItem(row, 0, name_item)
            self.matTable.setItem(row, 1, QtWidgets.QTableWidgetItem(mat_data.get("oofem_type", "")))
            self.matTable.setItem(row, 2, QtWidgets.QTableWidgetItem(mat_data.get("assigned_group", "")))
        self._block_signals = False
        self.populateMaterialDetails() # Clear details pane if no selection

    def populateMaterialDetails(self):
        """Populates the property editor based on the selected material."""
        self._block_signals = True
        self.matPropsTable.setRowCount(0)
        
        selected_items = self.matTable.selectedItems()
        if not selected_items:
            self._block_signals = False
            return

        mat_id = selected_items[0].data(Qt.UserRole)
        mat_data = next((m for m in self.state['materials'] if m['id'] == mat_id), None)
        if not mat_data:
            self._block_signals = False
            return

        # Find the template for this material type
        template = next((t for t in self.material_templates if t['oofem_name'] == mat_data['oofem_type']), None)
        if not template:
            self._block_signals = False
            return

        # Populate the properties table
        current_params = mat_data.get("params", {})
        for param_def in template.get("params", []):
            row = self.matPropsTable.rowCount()
            self.matPropsTable.insertRow(row)
            
            is_optional = param_def.get("optional", False)
            display_name = param_def['name']
            if is_optional:
                display_name += " (optional)"

            name_item = QtWidgets.QTableWidgetItem(display_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setData(Qt.UserRole, param_def['key']) # Store key (e.g., "E")
            # Store the expected data type for later conversion. Default to 'float' for backward compatibility.
            name_item.setData(Qt.UserRole + 1, param_def.get('type', 'float'))
            
            value = current_params.get(param_def['key'], param_def.get('default', ''))
            value_item = QtWidgets.QTableWidgetItem(str(value))
            name_item.setData(Qt.UserRole + 2, is_optional)

            # Set tooltip if a description is available in the template
            description = param_def.get("description")
            if description:
                name_item.setToolTip(description)
                value_item.setToolTip(description)

            self.matPropsTable.setItem(row, 0, name_item)
            self.matPropsTable.setItem(row, 1, value_item)
        
        self._block_signals = False

    def addMaterial(self):
        """Opens a dialog to add a new material instance."""
        mesh_groups = self.getMeshGroups()
        new_mat_data = OOFEMMaterialDialog.run(self.material_templates, mesh_groups, parent=self)

        if new_mat_data:
            # Add unique ID and default parameters
            new_mat_data['id'] = str(uuid.uuid4())
            new_mat_data['params'] = {}
            template = next((t for t in self.material_templates if t['oofem_name'] == new_mat_data['oofem_type']), None)
            if template:
                for p in template.get('params', []):
                    # Only add a parameter if it has a defined default value.
                    if 'default' in p:
                        new_mat_data['params'][p['key']] = p['default']

            self.state["materials"].append(new_mat_data)
            self.populateMaterials()

    def removeMaterial(self):
        """Removes the selected material from the state."""
        selected_items = self.matTable.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(self, "Warning", "No material selected to remove.")
            return

        mat_id = selected_items[0].data(Qt.UserRole)
        self.state['materials'] = [m for m in self.state['materials'] if m.get('id') != mat_id]
        self.populateMaterials()

    # ---------------------------
    # Boundary Conditions
    # ---------------------------
    def populateBCs(self):
        """Populates the main BC table from the plugin state."""
        self._block_signals = True
        self.bcTable.setRowCount(0)
        for i, bc_data in enumerate(self.state.get("bcs", [])):
            row = self.bcTable.rowCount()
            self.bcTable.insertRow(row)
            
            name_item = QtWidgets.QTableWidgetItem(bc_data.get("name", "Unnamed"))
            name_item.setData(Qt.UserRole, bc_data.get("id"))
            
            self.bcTable.setItem(row, 0, name_item)
            self.bcTable.setItem(row, 1, QtWidgets.QTableWidgetItem(bc_data.get("oofem_type", "")))
            self.bcTable.setItem(row, 2, QtWidgets.QTableWidgetItem(bc_data.get("assigned_group", "")))
        self._block_signals = False
        self.populateBCDetails()

    def populateBCDetails(self):
        """Populates the property editor based on the selected BC."""
        self._block_signals = True
        self.bcPropsTable.setRowCount(0)
        
        selected_items = self.bcTable.selectedItems()
        if not selected_items:
            self._block_signals = False
            return

        bc_id = selected_items[0].data(Qt.UserRole)
        bc_data = next((m for m in self.state['bcs'] if m['id'] == bc_id), None)
        if not bc_data:
            self._block_signals = False
            return

        template = next((t for t in self.bc_templates if t['oofem_name'] == bc_data['oofem_type']), None)
        if not template:
            self._block_signals = False
            return

        current_params = bc_data.get("params", {})
        for param_def in template.get("params", []):
            row = self.bcPropsTable.rowCount()
            self.bcPropsTable.insertRow(row)
            
            is_optional = param_def.get("optional", False)
            display_name = param_def['name']
            if is_optional:
                display_name += " (optional)"

            name_item = QtWidgets.QTableWidgetItem(display_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setData(Qt.UserRole, param_def['key'])
            name_item.setData(Qt.UserRole + 1, param_def.get('type', 'float'))
            name_item.setData(Qt.UserRole + 2, is_optional)
            
            value = current_params.get(param_def['key'], param_def.get('default', ''))
            value_item = QtWidgets.QTableWidgetItem(str(value))

            description = param_def.get("description")
            if description:
                name_item.setToolTip(description)
                value_item.setToolTip(description)

            self.bcPropsTable.setItem(row, 0, name_item)
            self.bcPropsTable.setItem(row, 1, value_item)
        
        self._block_signals = False

    def addBC(self):
        """Opens a dialog to add a new BC instance."""
        mesh_groups = self.getMeshGroups()
        new_bc_data = OOFEMBCDialog.run(self.bc_templates, mesh_groups, parent=self)

        if new_bc_data:
            new_bc_data['id'] = str(uuid.uuid4())
            new_bc_data['params'] = {}
            template = next((t for t in self.bc_templates if t['oofem_name'] == new_bc_data['oofem_type']), None)
            if template:
                for p in template.get('params', []):
                    if 'default' in p:
                        new_bc_data['params'][p['key']] = p['default']

            self.state["bcs"].append(new_bc_data)
            self.populateBCs()

    def removeBC(self):
        """Removes the selected BC from the state."""
        selected_items = self.bcTable.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(self, "Warning", "No BC selected to remove.")
            return

        bc_id = selected_items[0].data(Qt.UserRole)
        self.state['bcs'] = [m for m in self.state['bcs'] if m.get('id') != bc_id]
        self.populateBCs()

    def onAnalysisPropertyChanged(self, row, column):
        """Updates the state when an analysis property value is changed."""
        if self._block_signals or column != 1:
            return

        analysis_data = self.state.get('analysis')
        if not analysis_data: return

        key_item = self.analysisPropsTable.item(row, 0)
        value_item = self.analysisPropsTable.item(row, 1)
        param_key = key_item.data(Qt.UserRole)
        param_type = key_item.data(Qt.UserRole + 1)
        is_optional = key_item.data(Qt.UserRole + 2)
        value_text = value_item.text().strip()

        if is_optional and not value_text:
            if param_key in analysis_data['params']:
                del analysis_data['params'][param_key]
            return

        new_value = None
        try:
            if param_type == 'float':
                new_value = float(value_text)
            elif param_type == 'int':
                new_value = int(value_text)
            elif param_type == 'string':
                new_value = str(value_text)
            else:
                new_value = str(value_text)
        except ValueError:
            print(f"Invalid value '{value_text}' for parameter '{param_key}' (expected type: {param_type}). Change not saved.")
            return
        analysis_data['params'][param_key] = new_value

    def onBCPropertyChanged(self, row, column):
        """Updates the state when a BC property value is changed."""
        if self._block_signals or column != 1:
            return

        selected_items = self.bcTable.selectedItems()
        if not selected_items: return

        bc_id = selected_items[0].data(Qt.UserRole)
        bc_data = next((m for m in self.state['bcs'] if m['id'] == bc_id), None)
        if not bc_data: return

        key_item = self.bcPropsTable.item(row, 0)
        value_item = self.bcPropsTable.item(row, 1)
        param_key = key_item.data(Qt.UserRole)
        param_type = key_item.data(Qt.UserRole + 1)
        is_optional = key_item.data(Qt.UserRole + 2)
        value_text = value_item.text().strip()

        if is_optional and not value_text:
            if param_key in bc_data['params']:
                del bc_data['params'][param_key]
            return

        new_value = None
        try:
            if param_type == 'float':
                new_value = float(value_text)
            elif param_type == 'int':
                new_value = int(value_text)
            elif param_type == 'string':
                new_value = str(value_text)
            else:
                new_value = str(value_text)
        except ValueError:
            print(f"Invalid value '{value_text}' for parameter '{param_key}' (expected type: {param_type}). Change not saved.")
            return
        bc_data['params'][param_key] = new_value


    def onMaterialPropertyChanged(self, row, column):
        """Updates the state when a material property value is changed."""
        if self._block_signals or column != 1:
            return

        selected_items = self.matTable.selectedItems()
        if not selected_items:
            return

        mat_id = selected_items[0].data(Qt.UserRole)
        mat_data = next((m for m in self.state['materials'] if m['id'] == mat_id), None)
        if not mat_data:
            return

        key_item = self.matPropsTable.item(row, 0)
        value_item = self.matPropsTable.item(row, 1)
        param_key = key_item.data(Qt.UserRole)
        
        param_type = key_item.data(Qt.UserRole + 1) # Retrieve the stored type
        is_optional = key_item.data(Qt.UserRole + 2)
        
        value_text = value_item.text().strip()

        # If the parameter is optional and the user cleared the value, remove it from the state
        if is_optional and not value_text:
            if param_key in mat_data['params']:
                del mat_data['params'][param_key]
                print(f"INFO: Optional parameter '{param_key}' was removed.")
            return

        new_value = None
        try:
            if param_type == 'float':
                new_value = float(value_text)
            elif param_type == 'int':
                new_value = int(value_text)
            elif param_type == 'string':
                new_value = str(value_text)
            # Future types like 'bool' or choice lists can be added here.
            else:
                # Default to string if type is unknown or not specified
                new_value = str(value_text)
        except ValueError:
            # Optionally, provide feedback to the user about the invalid input
            print(f"Invalid value '{value_text}' for parameter '{param_key}' (expected type: {param_type}). Change not saved.")
            # Revert the change in the UI? For now, we just don't save it.
            return
        mat_data['params'][param_key] = new_value

    # ---------------------------
    # State Management
    # ---------------------------
    def saveState(self):
        if self.study is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Plugin not initialized. Click Refresh first.")
            return

        new_map = {}
        for row in range(self.elemTable.rowCount()):
            salome_type = self.elemTable.item(row, 0).text()
            oofem_type = self.elemTable.item(row, 1).text()
            new_map[salome_type] = oofem_type

        # Update state dictionary
        self.state["element_mapping"] = new_map
        # self.state["materials"] and self.state["bcs"] are updated dynamically.

        OOFEMState.save(self.study, self.state)

        QtWidgets.QMessageBox.information(self, "Saved", "Plugin state saved to the Salome study.")

    # ---------------------------
    # Export
    # ---------------------------
    def export(self):
        if self.study is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Plugin not fully initialized. Click Refresh first.")
            return

        mesh_id = self.meshCombo.currentData()
        if not mesh_id:
            QtWidgets.QMessageBox.warning(self, "Error", "No mesh selected for export.")
            return

        try:
            import salome
            from OOFEMSalomePlugin.OOFEMExporter import OOFEMExporter

            mesh = salome.IDToObject(mesh_id)
            if not mesh:
                QtWidgets.QMessageBox.warning(self, "Error", "The selected object could not be identified as a valid mesh.")
                return

            study = salome.myStudy
            so = salome.myStudy.FindObjectID(mesh_id)

            # Let user choose where to save the file
            default_name = f"{so.GetName()}.in"
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export OOFEM Input File", default_name, "OOFEM Input Files (*.in);;All Files (*)")

            if not filename:
                return  # User cancelled

            # Create and run the exporter
            exporter = OOFEMExporter(
                mesh,
                self.state.get("element_mapping", {}),
                self.state.get("materials", []),
                self.state.get("bcs", []),
                self.bc_templates,
                self.state.get("analysis", {})
            )
            exporter.export(filename)

            QtWidgets.QMessageBox.information(self, "Export Successful", f"Mesh exported successfully to:\n{filename}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An unexpected error occurred during export:\n{e}")
            traceback.print_exc()  # Also print to console
