# src/OOFEMSalomePlugin/OOFEMTimeFunctionDialog.py

from PyQt5 import QtWidgets

class OOFEMTimeFunctionDialog(QtWidgets.QDialog):
    """
    A dialog for creating and editing a time function instance.
    """
    def __init__(self, tf_templates, existing_tf=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Time Function Definition")

        self.tf_templates = tf_templates

        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        self.nameEdit = QtWidgets.QLineEdit()
        self.typeCombo = QtWidgets.QComboBox()

        form_layout.addRow("Instance Name:", self.nameEdit)
        form_layout.addRow("Time Function Type:", self.typeCombo)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.typeCombo.addItems([t['display_name'] for t in self.tf_templates])

        if existing_tf:
            self.nameEdit.setText(existing_tf.get("name", ""))
            
            oofem_type = existing_tf.get("oofem_type")
            type_index = next((i for i, t in enumerate(self.tf_templates) if t['oofem_name'] == oofem_type), -1)
            if type_index != -1:
                self.typeCombo.setCurrentIndex(type_index)

    def get_data(self):
        """Returns the configured time function data as a dictionary."""
        selected_template = self.tf_templates[self.typeCombo.currentIndex()]

        return {
            "name": self.nameEdit.text(),
            "oofem_type": selected_template['oofem_name'],
        }

    @staticmethod
    def run(tf_templates, existing_tf=None, parent=None):
        """Static method to create, run, and return data from the dialog."""
        dialog = OOFEMTimeFunctionDialog(tf_templates, existing_tf, parent)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.get_data()
        return None