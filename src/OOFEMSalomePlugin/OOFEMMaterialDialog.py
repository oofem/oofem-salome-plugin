# src/OOFEMSalomePlugin/OOFEMMaterialDialog.py

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

class OOFEMMaterialDialog(QtWidgets.QDialog):
    """
    A dialog for creating and editing a material instance.
    Handles name, type, group assignment, and the optional element mapping override.
    """
    def __init__(self, material_templates, existing_material=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Material Definition")

        self.material_templates = material_templates

        # --- Layout ---
        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        # --- UI Fields ---
        self.nameEdit = QtWidgets.QLineEdit()
        self.typeCombo = QtWidgets.QComboBox()

        form_layout.addRow("Instance Name:", self.nameEdit)
        form_layout.addRow("OOFEM Material Type:", self.typeCombo)

        # --- Dialog Buttons ---
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # --- Populate UI ---
        self.typeCombo.addItems([t['display_name'] for t in self.material_templates])

        # If editing, populate fields with existing data
        if existing_material:
            self.nameEdit.setText(existing_material.get("name", ""))
            
            # Select material type
            oofem_type = existing_material.get("oofem_type")
            type_index = next((i for i, t in enumerate(self.material_templates) if t['oofem_name'] == oofem_type), -1)
            if type_index != -1:
                self.typeCombo.setCurrentIndex(type_index)

    def get_data(self):
        """Returns the configured material data as a dictionary."""
        selected_template = self.material_templates[self.typeCombo.currentIndex()]

        return {
            "name": self.nameEdit.text(),
            "oofem_type": selected_template['oofem_name'],
        }

    @staticmethod
    def run(material_templates, existing_material=None, parent=None):
        """Static method to create, run, and return data from the dialog."""
        dialog = OOFEMMaterialDialog(material_templates, existing_material, parent)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.get_data()
        return None