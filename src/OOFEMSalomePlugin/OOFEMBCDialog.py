# src/OOFEMSalomePlugin/OOFEMBCDialog.py

from PyQt5 import QtWidgets

class OOFEMBCDialog(QtWidgets.QDialog):
    """
    A dialog for creating and editing a boundary condition instance.
    """
    def __init__(self, bc_templates, mesh_groups, time_function_map, existing_bc=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Boundary Condition Definition")

        self.bc_templates = bc_templates
        self.mesh_groups = mesh_groups
        self.time_function_map = time_function_map

        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        self.nameEdit = QtWidgets.QLineEdit()
        self.typeCombo = QtWidgets.QComboBox()
        self.groupCombo = QtWidgets.QComboBox()
        self.tfCombo = QtWidgets.QComboBox()

        form_layout.addRow("Instance Name:", self.nameEdit)
        form_layout.addRow("OOFEM BC Type:", self.typeCombo)
        form_layout.addRow("Assign to Mesh Group:", self.groupCombo)
        form_layout.addRow("Time Function:", self.tfCombo)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.typeCombo.addItems([t['display_name'] for t in self.bc_templates])
        self.groupCombo.addItems(self.mesh_groups)

        # Populate time function dropdown
        for tf in self.time_function_map:
            self.tfCombo.addItem(tf.get('name', 'Unnamed'), tf.get('id'))

        if existing_bc:
            self.nameEdit.setText(existing_bc.get("name", ""))
            
            oofem_type = existing_bc.get("oofem_type")
            type_index = next((i for i, t in enumerate(self.bc_templates) if t['oofem_name'] == oofem_type), -1)
            if type_index != -1:
                self.typeCombo.setCurrentIndex(type_index)

            group_name = existing_bc.get("assigned_group", "")
            group_index = self.groupCombo.findText(group_name)
            if group_index != -1:
                self.groupCombo.setCurrentIndex(group_index)
            
            tf_id = existing_bc.get("time_function_id")
            tf_index = self.tfCombo.findData(tf_id)
            if tf_index != -1:
                self.tfCombo.setCurrentIndex(tf_index)

    def get_data(self):
        """Returns the configured BC data as a dictionary."""
        selected_template = self.bc_templates[self.typeCombo.currentIndex()]

        return {
            "name": self.nameEdit.text(),
            "oofem_type": selected_template['oofem_name'],
            "assigned_group": self.groupCombo.currentText(),
            "time_function_id": self.tfCombo.currentData(),
        }

    @staticmethod
    def run(bc_templates, mesh_groups, time_function_map, existing_bc=None, parent=None):
        """Static method to create, run, and return data from the dialog."""
        if not time_function_map:
            QtWidgets.QMessageBox.warning(parent, "No Time Functions", "You must define at least one time function before creating a boundary condition.")
            return None
        dialog = OOFEMBCDialog(bc_templates, mesh_groups, time_function_map, existing_bc, parent)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.get_data()
        return None