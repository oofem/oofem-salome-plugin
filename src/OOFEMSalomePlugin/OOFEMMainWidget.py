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
from OOFEMSalomePlugin.OOFEMCrossSectionDialog import OOFEMCrossSectionDialog
from OOFEMSalomePlugin.OOFEMBCDialog import OOFEMBCDialog


class OOFEMMainWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Defer study and state loading until populateAll() is called.
        self.study = None
        self.state = {}
        self.material_templates = []
        self.analysis_templates = []
        self.cs_templates = []
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
        self.addMatBtn = QtWidgets.QPushButton("Add")
        self.addMatBtn.clicked.connect(self.addMaterial)
        self.editMatBtn = QtWidgets.QPushButton("Edit")
        self.editMatBtn.clicked.connect(self.editMaterial)
        self.removeMatBtn = QtWidgets.QPushButton("Remove")
        self.removeMatBtn.clicked.connect(self.removeMaterial)
        mat_btn_layout.addWidget(self.addMatBtn)
        mat_btn_layout.addWidget(self.editMatBtn)
        mat_btn_layout.addWidget(self.removeMatBtn)
        mat_btn_layout.addStretch()
        mat_layout.addLayout(mat_btn_layout)

        # Table of defined materials
        self.matTable = QtWidgets.QTableWidget()
        self.matTable.setColumnCount(2)
        self.matTable.setHorizontalHeaderLabels(["Name", "OOFEM Type"])
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

        # Tab 4: Cross Sections
        cs_tab = QtWidgets.QWidget()
        cs_layout = QtWidgets.QVBoxLayout(cs_tab)

        cs_btn_layout = QtWidgets.QHBoxLayout()
        self.addCSBtn = QtWidgets.QPushButton("Add")
        self.addCSBtn.clicked.connect(self.addCrossSection)
        self.editCSBtn = QtWidgets.QPushButton("Edit")
        self.editCSBtn.clicked.connect(self.editCrossSection)
        self.removeCSBtn = QtWidgets.QPushButton("Remove")
        self.removeCSBtn.clicked.connect(self.removeCrossSection)
        cs_btn_layout.addWidget(self.addCSBtn)
        cs_btn_layout.addWidget(self.editCSBtn)
        cs_btn_layout.addWidget(self.removeCSBtn)
        cs_btn_layout.addStretch()
        cs_layout.addLayout(cs_btn_layout)

        self.csTable = QtWidgets.QTableWidget()
        self.csTable.setColumnCount(4)
        self.csTable.setHorizontalHeaderLabels(["Name", "Type", "Material", "Assigned Group"])
        self.csTable.itemSelectionChanged.connect(self.populateCrossSectionDetails)
        self.csTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.csTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        cs_layout.addWidget(self.csTable)

        cs_props_group = QtWidgets.QGroupBox("Cross Section Properties (select a section above)")
        cs_props_layout = QtWidgets.QVBoxLayout(cs_props_group)
        self.csPropsTable = QtWidgets.QTableWidget()
        self.csPropsTable.setColumnCount(2)
        self.csPropsTable.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.csPropsTable.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.csPropsTable.cellChanged.connect(self.onCrossSectionPropertyChanged)
        cs_props_layout.addWidget(self.csPropsTable)
        cs_layout.addWidget(cs_props_group)

        cs_layout.addStretch()
        self.tabs.insertTab(3, cs_tab, "Cross Sections") # Insert before BCs


        # Tab 4: Boundary Conditions
        bc_tab = QtWidgets.QWidget()
        bc_layout = QtWidgets.QVBoxLayout(bc_tab)

        bc_btn_layout = QtWidgets.QHBoxLayout()
        self.addBCBtn = QtWidgets.QPushButton("Add")
        self.addBCBtn.clicked.connect(self.addBC)
        self.editBCBtn = QtWidgets.QPushButton("Edit")
        # self.editBCBtn.clicked.connect(self.editBC) # Placeholder for future
        self.removeBCBtn = QtWidgets.QPushButton("Remove")
        self.removeBCBtn.clicked.connect(self.removeBC)
        bc_btn_layout.addWidget(self.addBCBtn)
        bc_btn_layout.addWidget(self.editBCBtn)
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

    def _format_param_value(self, value):
        """Formats a parameter value for display in the UI."""
        if isinstance(value, list):
            return " ".join(map(str, value))
        return str(value)

    def _parse_param_value(self, value_text, param_type):
        """Parses a string value from a property table into the correct Python type."""
        value_text = value_text.strip()

        if param_type == 'float':
            return float(value_text)
        elif param_type == 'int':
            return int(value_text)
        elif param_type == 'string':
            return str(value_text)
        elif param_type == 'intarray':
            # Handles space or comma separated values
            if not value_text: return []
            return [int(v) for v in value_text.replace(',', ' ').split()]
        elif param_type == 'floatarray':
            # Handles space or comma separated values
            if not value_text: return []
            return [float(v) for v in value_text.replace(',', ' ').split()]
        else:
            # Default to string if type is unknown
            return str(value_text)

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

    def loadCrossSectionTemplates(self):
        """Loads cross section definitions from the JSON file."""
        try:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(plugin_dir, "OOFEMCrossSections.json")
            with open(json_path, 'r') as f:
                data = json.load(f)
                self.cs_templates = data.get("cross_sections", [])
        except Exception as e:
            print(f"Error loading cross section templates: {e}")
            self.cs_templates = []

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
        if "cross_sections" not in self.state:
            self.state["cross_sections"] = []
        if "analysis" not in self.state:
            # Set a default analysis if none is defined
            self.state["analysis"] = {
                "oofem_type": "StaticStructural",
                "params": {"nsteps": 1}
            }
        if "bcs" not in self.state:
            self.state["bcs"] = []

        self.loadCrossSectionTemplates()
        self.loadAnalysisTemplates()
        self.loadMaterialTemplates()
        self.loadBCTemplates()
        self.populateMeshes()
        self.populateAnalysis()
        self.populateElementMapping()
        self.populateMaterials()
        self.populateCrossSections()
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
            value_item = QtWidgets.QTableWidgetItem(self._format_param_value(value))

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
            name_item.setData(Qt.UserRole + 1, param_def.get('type', 'string'))
            
            name_item.setData(Qt.UserRole + 2, is_optional)
            value = current_params.get(param_def['key'], param_def.get('default', ''))
            value_item = QtWidgets.QTableWidgetItem(self._format_param_value(value))

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
        new_mat_data = OOFEMMaterialDialog.run(self.material_templates, parent=self)

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

    def editMaterial(self):
        """Opens a dialog to edit the selected material instance."""
        selected_items = self.matTable.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(self, "Warning", "No material selected to edit.")
            return

        mat_id = selected_items[0].data(Qt.UserRole)
        mat_data = next((m for m in self.state['materials'] if m.get('id') == mat_id), None)
        if not mat_data: return

        updated_data = OOFEMMaterialDialog.run(self.material_templates, existing_material=mat_data, parent=self)

        if updated_data:
            mat_data.update(updated_data)
            self.populateMaterials()
            for row in range(self.matTable.rowCount()):
                if self.matTable.item(row, 0).data(Qt.UserRole) == mat_id:
                    self.matTable.selectRow(row)
                    break

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
    # Cross Sections
    # ---------------------------
    def populateCrossSections(self):
        """Populates the main cross section table from the plugin state."""
        self._block_signals = True
        self.csTable.setRowCount(0)
        # Create a quick lookup map for material names
        mat_id_to_name = {m['id']: m.get('name', 'Unnamed') for m in self.state.get("materials", [])}

        for cs_data in self.state.get("cross_sections", []):
            row = self.csTable.rowCount()
            self.csTable.insertRow(row)

            name_item = QtWidgets.QTableWidgetItem(cs_data.get("name", "Unnamed"))
            name_item.setData(Qt.UserRole, cs_data.get("id"))

            material_name = mat_id_to_name.get(cs_data.get("material_id"), "INVALID/DELETED")

            self.csTable.setItem(row, 0, name_item)
            self.csTable.setItem(row, 1, QtWidgets.QTableWidgetItem(cs_data.get("oofem_type", "")))
            self.csTable.setItem(row, 2, QtWidgets.QTableWidgetItem(material_name))
            self.csTable.setItem(row, 3, QtWidgets.QTableWidgetItem(cs_data.get("assigned_group", "")))
        self._block_signals = False
        self.populateCrossSectionDetails()

    def populateCrossSectionDetails(self):
        """Populates the property editor based on the selected cross section."""
        self._block_signals = True
        self.csPropsTable.setRowCount(0)

        selected_items = self.csTable.selectedItems()
        if not selected_items:
            self._block_signals = False
            return

        cs_id = selected_items[0].data(Qt.UserRole)
        cs_data = next((cs for cs in self.state['cross_sections'] if cs['id'] == cs_id), None)
        if not cs_data:
            self._block_signals = False
            return

        template = next((t for t in self.cs_templates if t['oofem_name'] == cs_data['oofem_type']), None)
        if not template:
            self._block_signals = False
            return

        current_params = cs_data.get("params", {})
        for param_def in template.get("params", []):
            row = self.csPropsTable.rowCount()
            self.csPropsTable.insertRow(row)

            is_optional = param_def.get("optional", False)
            display_name = param_def['name']
            if is_optional: display_name += " (optional)"

            name_item = QtWidgets.QTableWidgetItem(display_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setData(Qt.UserRole, param_def['key'])
            name_item.setData(Qt.UserRole + 1, param_def.get('type', 'string'))
            name_item.setData(Qt.UserRole + 2, is_optional)

            value = current_params.get(param_def['key'], param_def.get('default', ''))
            value_item = QtWidgets.QTableWidgetItem(self._format_param_value(value))

            description = param_def.get("description")
            if description:
                name_item.setToolTip(description)
                value_item.setToolTip(description)

            self.csPropsTable.setItem(row, 0, name_item)
            self.csPropsTable.setItem(row, 1, value_item)

        self._block_signals = False

    def addCrossSection(self):
        """Opens a dialog to add a new cross section instance."""
        mesh_groups = self.getMeshGroups()
        materials = self.state.get("materials", [])
        salome_types = self.state.get("element_mapping", {}).keys()
        new_cs_data = OOFEMCrossSectionDialog.run(self.cs_templates, materials, mesh_groups, salome_types, parent=self)

        if new_cs_data:
            new_cs_data['id'] = str(uuid.uuid4())
            new_cs_data['params'] = {}
            template = next((t for t in self.cs_templates if t['oofem_name'] == new_cs_data['oofem_type']), None)
            if template:
                for p in template.get('params', []):
                    if 'default' in p:
                        new_cs_data['params'][p['key']] = p['default']
            self.state["cross_sections"].append(new_cs_data)
            self.populateCrossSections()

    def editCrossSection(self):
        """Opens a dialog to edit the selected cross section instance."""
        selected_items = self.csTable.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(self, "Warning", "No cross section selected to edit.")
            return

        cs_id = selected_items[0].data(Qt.UserRole)
        cs_data = next((cs for cs in self.state['cross_sections'] if cs.get('id') == cs_id), None)
        if not cs_data: return

        mesh_groups = self.getMeshGroups()
        materials = self.state.get("materials", [])
        salome_types = self.state.get("element_mapping", {}).keys()
        
        updated_data = OOFEMCrossSectionDialog.run(self.cs_templates, materials, mesh_groups, salome_types, existing_cs=cs_data, parent=self)

        if updated_data:
            cs_data.update(updated_data)
            self.populateCrossSections()
            for row in range(self.csTable.rowCount()):
                if self.csTable.item(row, 0).data(Qt.UserRole) == cs_id:
                    self.csTable.selectRow(row)
                    break

    def removeCrossSection(self):
        """Removes the selected cross section from the state."""
        selected_items = self.csTable.selectedItems()
        if not selected_items:
            return
        cs_id = selected_items[0].data(Qt.UserRole)
        self.state['cross_sections'] = [cs for cs in self.state['cross_sections'] if cs.get('id') != cs_id]
        self.populateCrossSections()

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
            name_item.setData(Qt.UserRole + 1, param_def.get('type', 'string'))
            name_item.setData(Qt.UserRole + 2, is_optional)
            
            value = current_params.get(param_def['key'], param_def.get('default', ''))
            value_item = QtWidgets.QTableWidgetItem(self._format_param_value(value))

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

        try:
            new_value = self._parse_param_value(value_text, param_type)
        except (ValueError, TypeError):
            print(f"Invalid value '{value_text}' for parameter '{param_key}' (expected type: {param_type}). Change not saved.")
            return
        analysis_data['params'][param_key] = new_value

    def onCrossSectionPropertyChanged(self, row, column):
        """Updates the state when a cross section property value is changed."""
        if self._block_signals or column != 1:
            return

        selected_items = self.csTable.selectedItems()
        if not selected_items: return

        cs_id = selected_items[0].data(Qt.UserRole)
        cs_data = next((cs for cs in self.state['cross_sections'] if cs['id'] == cs_id), None)
        if not cs_data: return

        key_item = self.csPropsTable.item(row, 0)
        value_item = self.csPropsTable.item(row, 1)
        param_key = key_item.data(Qt.UserRole)
        param_type = key_item.data(Qt.UserRole + 1)
        is_optional = key_item.data(Qt.UserRole + 2)
        value_text = value_item.text().strip()

        if is_optional and not value_text:
            if param_key in cs_data['params']:
                del cs_data['params'][param_key]
            return

        try:
            new_value = self._parse_param_value(value_text, param_type)
        except (ValueError, TypeError):
            print(f"Invalid value '{value_text}' for parameter '{param_key}' (expected type: {param_type}). Change not saved.")
            return
        cs_data['params'][param_key] = new_value

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

        try:
            new_value = self._parse_param_value(value_text, param_type)
        except (ValueError, TypeError):
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

        try:
            new_value = self._parse_param_value(value_text, param_type)
        except (ValueError, TypeError):
            print(f"Invalid value '{value_text}' for parameter '{param_key}' (expected type: {param_type}). Change not saved.")
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

            # Get study info to pass to the exporter for the file header
            study_name = "Unknown"
            study_path = ""
            if self.study:
                # Get study name: Try method first, then attribute
                if hasattr(self.study, "GetStudyName"):
                    study_name = self.study.GetStudyName()
                elif hasattr(self.study, "Name"):
                    study_name = self.study.Name
                # Get study path: Try method first, then attribute
                if hasattr(self.study, "GetStudyPath"):
                    study_path = self.study.GetStudyPath()
                elif hasattr(self.study, "URL"):
                    study_path = self.study.URL

            # Create and run the exporter
            exporter = OOFEMExporter(
                mesh,
                self.state.get("element_mapping", {}),
                self.state.get("materials", []),
                self.state.get("cross_sections", []),
                self.state.get("bcs", []),
                self.bc_templates,
                self.state.get("analysis", {}),
                study_name,
                study_path
            )
            exporter.export(filename)

            QtWidgets.QMessageBox.information(self, "Export Successful", f"Mesh exported successfully to:\n{filename}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An unexpected error occurred during export:\n{e}")
            traceback.print_exc()  # Also print to console
