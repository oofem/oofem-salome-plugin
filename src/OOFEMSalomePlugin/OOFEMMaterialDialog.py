# src/OOFEMSalomePlugin/OOFEMMaterialDialog.py

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

class OOFEMMaterialDialog(QtWidgets.QDialog):
    """
    A dialog for creating and editing a material instance.
    Handles name, type, group assignment, and the optional element mapping override.
    """
    def __init__(self, material_templates, mesh_groups, existing_material=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Material Definition")

        self.material_templates = material_templates
        self.mesh_groups = mesh_groups

        # --- Layout ---
        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        # --- UI Fields ---
        self.nameEdit = QtWidgets.QLineEdit()
        self.typeCombo = QtWidgets.QComboBox()
        self.groupCombo = QtWidgets.QComboBox()

        form_layout.addRow("Instance Name:", self.nameEdit)
        form_layout.addRow("OOFEM Material Type:", self.typeCombo)
        form_layout.addRow("Assign to Mesh Group:", self.groupCombo)

        # --- Element Mapping Override Section ---
        self.overrideGroup = QtWidgets.QGroupBox("Element Mapping Override")
        self.overrideGroup.setCheckable(True)
        self.overrideGroup.setChecked(False)
        override_layout = QtWidgets.QVBoxLayout(self.overrideGroup)
        
        self.overrideTable = QtWidgets.QTableWidget()
        self.overrideTable.setColumnCount(2)
        self.overrideTable.setHorizontalHeaderLabels(["Salome Type", "OOFEM Type"])
        override_layout.addWidget(self.overrideTable)
        layout.addWidget(self.overrideGroup)

        # --- Dialog Buttons ---
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # --- Populate UI ---
        self.typeCombo.addItems([t['display_name'] for t in self.material_templates])
        self.groupCombo.addItems(["<None>"] + self.mesh_groups)

        # If editing, populate fields with existing data
        if existing_material:
            self.nameEdit.setText(existing_material.get("name", ""))
            
            # Select material type
            oofem_type = existing_material.get("oofem_type")
            type_index = next((i for i, t in enumerate(self.material_templates) if t['oofem_name'] == oofem_type), -1)
            if type_index != -1:
                self.typeCombo.setCurrentIndex(type_index)

            # Select assigned group
            group_name = existing_material.get("assigned_group", "<None>")
            group_index = self.groupCombo.findText(group_name)
            if group_index != -1:
                self.groupCombo.setCurrentIndex(group_index)

            # Populate override mapping
            override_map = existing_material.get("element_mapping_override")
            if override_map:
                self.overrideGroup.setChecked(True)
                self.overrideTable.setRowCount(0)
                for salome_type, oofem_type in override_map.items():
                    row = self.overrideTable.rowCount()
                    self.overrideTable.insertRow(row)
                    self.overrideTable.setItem(row, 0, QtWidgets.QTableWidgetItem(salome_type))
                    self.overrideTable.setItem(row, 1, QtWidgets.QTableWidgetItem(oofem_type))

    def get_data(self):
        """Returns the configured material data as a dictionary."""
        selected_template = self.material_templates[self.typeCombo.currentIndex()]
        
        override_map = None
        if self.overrideGroup.isChecked():
            override_map = {}
            for row in range(self.overrideTable.rowCount()):
                salome_type = self.overrideTable.item(row, 0).text()
                oofem_type = self.overrideTable.item(row, 1).text()
                if salome_type and oofem_type:
                    override_map[salome_type] = oofem_type

        return {
            "name": self.nameEdit.text(),
            "oofem_type": selected_template['oofem_name'],
            "assigned_group": self.groupCombo.currentText() if self.groupCombo.currentText() != "<None>" else None,
            "element_mapping_override": override_map
        }

    @staticmethod
    def run(material_templates, mesh_groups, existing_material=None, parent=None):
        """Static method to create, run, and return data from the dialog."""
        dialog = OOFEMMaterialDialog(material_templates, mesh_groups, existing_material, parent)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.get_data()
        return None