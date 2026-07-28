# src/OOFEMSalomePlugin/OOFEMBCDialog.py

from PyQt5 import QtWidgets

class OOFEMBCDialog(QtWidgets.QDialog):
    """
    A dialog for creating and editing a boundary condition instance.
    """
    def __init__(self, bc_templates, mesh_groups, existing_bc=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Boundary Condition Definition")

        self.bc_templates = bc_templates
        self.mesh_groups = mesh_groups

        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        self.nameEdit = QtWidgets.QLineEdit()
        self.typeCombo = QtWidgets.QComboBox()
        self.groupCombo = QtWidgets.QComboBox()

        form_layout.addRow("Instance Name:", self.nameEdit)
        form_layout.addRow("OOFEM BC Type:", self.typeCombo)
        form_layout.addRow("Assign to Mesh Group:", self.groupCombo)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.typeCombo.addItems([t['display_name'] for t in self.bc_templates])
        self.groupCombo.addItems(["<None>"] + self.mesh_groups)

        if existing_bc:
            self.nameEdit.setText(existing_bc.get("name", ""))
            
            oofem_type = existing_bc.get("oofem_type")
            type_index = next((i for i, t in enumerate(self.bc_templates) if t['oofem_name'] == oofem_type), -1)
            if type_index != -1:
                self.typeCombo.setCurrentIndex(type_index)

            group_name = existing_bc.get("assigned_group", "<None>")
            group_index = self.groupCombo.findText(group_name)
            if group_index != -1:
                self.groupCombo.setCurrentIndex(group_index)

    def get_data(self):
        """Returns the configured BC data as a dictionary."""
        selected_template = self.bc_templates[self.typeCombo.currentIndex()]
        
        return {
            "name": self.nameEdit.text(),
            "oofem_type": selected_template['oofem_name'],
            "assigned_group": self.groupCombo.currentText() if self.groupCombo.currentText() != "<None>" else None,
        }

    @staticmethod
    def run(bc_templates, mesh_groups, existing_bc=None, parent=None):
        """Static method to create, run, and return data from the dialog."""
        dialog = OOFEMBCDialog(bc_templates, mesh_groups, existing_bc, parent)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.get_data()
        return None