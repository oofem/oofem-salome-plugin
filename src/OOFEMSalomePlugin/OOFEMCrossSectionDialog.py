# src/OOFEMSalomePlugin/OOFEMCrossSectionDialog.py

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

class OOFEMCrossSectionDialog(QtWidgets.QDialog):
    """
    A dialog for creating a cross section instance, which links a material
    to a mesh group and defines its geometric/kinematic properties.
    """
    def __init__(self, cs_templates, material_map, mesh_groups, salome_element_types, existing_cs=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cross Section Definition")

        self.cs_templates = cs_templates
        self.material_map = material_map
        self.mesh_groups = mesh_groups
        self.salome_element_types = salome_element_types

        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        self.nameEdit = QtWidgets.QLineEdit()
        self.typeCombo = QtWidgets.QComboBox()
        self.materialCombo = QtWidgets.QComboBox()
        self.groupCombo = QtWidgets.QComboBox()

        form_layout.addRow("Instance Name:", self.nameEdit)
        form_layout.addRow("Cross Section Type:", self.typeCombo)
        form_layout.addRow("Use Material:", self.materialCombo)
        form_layout.addRow("Assign to Mesh Group:", self.groupCombo)

        # --- Element Mapping Override Section ---
        self.overrideGroup = QtWidgets.QGroupBox("Element Mapping Override")
        self.overrideGroup.setCheckable(True)
        self.overrideGroup.setChecked(False)
        override_layout = QtWidgets.QVBoxLayout(self.overrideGroup)
        
        self.overrideTable = QtWidgets.QTableWidget()
        self.overrideTable.setColumnCount(2)
        self.overrideTable.setHorizontalHeaderLabels(["Salome Type", "OOFEM Type"])
        self.overrideTable.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        override_layout.addWidget(self.overrideTable)
        layout.addWidget(self.overrideGroup)


        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Populate dropdowns
        self.typeCombo.addItems([t['display_name'] for t in self.cs_templates])
        # For materials, show name and store its unique ID
        for mat in self.material_map:
            self.materialCombo.addItem(mat.get('name', 'Unnamed'), mat.get('id'))
        self.groupCombo.addItems(self.mesh_groups) # Assuming group is required

        # Populate override table with available Salome types
        self.overrideTable.setRowCount(0)
        for salome_type in sorted(self.salome_element_types):
            row = self.overrideTable.rowCount()
            self.overrideTable.insertRow(row)
            name_item = QtWidgets.QTableWidgetItem(salome_type)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.overrideTable.setItem(row, 0, name_item)
            self.overrideTable.setItem(row, 1, QtWidgets.QTableWidgetItem("")) # Empty for user input

        if existing_cs:
            self.nameEdit.setText(existing_cs.get("name", ""))
            
            oofem_type = existing_cs.get("oofem_type")
            type_index = next((i for i, t in enumerate(self.cs_templates) if t['oofem_name'] == oofem_type), -1)
            if type_index != -1:
                self.typeCombo.setCurrentIndex(type_index)

            material_id = existing_cs.get("material_id")
            mat_index = self.materialCombo.findData(material_id)
            if mat_index != -1:
                self.materialCombo.setCurrentIndex(mat_index)

            group_name = existing_cs.get("assigned_group", "")
            group_index = self.groupCombo.findText(group_name)
            if group_index != -1:
                self.groupCombo.setCurrentIndex(group_index)
            
            # Populate override mapping
            override_map = existing_cs.get("element_mapping_override")
            if override_map:
                self.overrideGroup.setChecked(True)
                for row in range(self.overrideTable.rowCount()):
                    salome_type = self.overrideTable.item(row, 0).text()
                    if salome_type in override_map:
                        self.overrideTable.setItem(row, 1, QtWidgets.QTableWidgetItem(override_map[salome_type]))

    def get_data(self):
        """Returns the configured cross section data as a dictionary."""
        selected_template = self.cs_templates[self.typeCombo.currentIndex()]
        
        override_map = None
        if self.overrideGroup.isChecked():
            override_map = {}
            for row in range(self.overrideTable.rowCount()):
                salome_type = self.overrideTable.item(row, 0).text()
                oofem_item = self.overrideTable.item(row, 1)
                if oofem_item and oofem_item.text().strip():
                    override_map[salome_type] = oofem_item.text().strip()

        return {
            "name": self.nameEdit.text(),
            "oofem_type": selected_template['oofem_name'],
            "material_id": self.materialCombo.currentData(),
            "assigned_group": self.groupCombo.currentText(),
            "element_mapping_override": override_map,
        }

    @staticmethod
    def run(cs_templates, material_map, mesh_groups, salome_element_types, existing_cs=None, parent=None):
        """Static method to create, run, and return data from the dialog."""
        if not material_map:
            QtWidgets.QMessageBox.warning(parent, "No Materials Defined", "You must define at least one material before creating a cross section.")
            return None
        if not mesh_groups:
            QtWidgets.QMessageBox.warning(parent, "No Mesh Groups", "The selected mesh has no groups. You must create groups to assign cross sections.")
            return None

        dialog = OOFEMCrossSectionDialog(cs_templates, material_map, mesh_groups, salome_element_types, existing_cs, parent)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.get_data()
        return None
