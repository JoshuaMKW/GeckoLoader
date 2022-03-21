import sys

from PySide6.QtCore import QMetaObject, QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QGridLayout, QLabel,
                               QLineEdit, QSizePolicy)

from geckoloader.fileutils import resource_path


class PrefWindow(QDialog):
    def __init__(self):
        super().__init__(None, Qt.WindowSystemMenuHint |
                         Qt.WindowTitleHint | Qt.WindowCloseButtonHint)

        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("Dialog")
        self.setFixedSize(300, 120)
        self.setModal(True)
        icon = QIcon()
        icon.addPixmap(QPixmap(
            str(resource_path("bin/icon.ico"))), QIcon.Normal, QIcon.Off)
        self.setWindowIcon(icon)

        # Buttonbox
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setFixedSize(280, 30)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")

        self.formLayoutWidget = QGridLayout(self)
        self.formLayoutWidget.setObjectName("formLayoutWidget")

        self.comboBoxLayout = QGridLayout()
        self.comboBoxLayout.setVerticalSpacing(10)
        self.comboBoxLayout.setObjectName("comboBoxLayout")

        # qtstyle box
        self.qtstyleSelect = QComboBox()
        self.qtstyleSelect.setObjectName("qtstyleSelect")
        self.comboBoxLayout.addWidget(self.qtstyleSelect, 1, 1, 1, 1)

        # qtstyle label
        self.qtstyleLabel = QLabel()
        self.qtstyleLabel.setObjectName("qtstyleLabel")
        self.comboBoxLayout.addWidget(self.qtstyleLabel, 1, 0, 1, 1)

        # qtdark theme
        self.qtdarkButton = QCheckBox()
        self.qtdarkButton.setObjectName("formalnaming")
        self.qtdarkButton.setText("Dark Theme")
        self.comboBoxLayout.addWidget(self.qtdarkButton, 2, 0, 1, 1)

        self.formLayoutWidget.addLayout(self.comboBoxLayout, 0, 0, 1, 1)
        self.formLayoutWidget.addWidget(self.buttonBox, 1, 0, 1, 1)

        self.retranslateUi()

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        QMetaObject.connectSlotsByName(self)

    def retranslateUi(self):
        self.setWindowTitle(QApplication.translate(
            "Dialog", "Preferences", None))
        self.qtstyleLabel.setText(
            QApplication.translate("Dialog", "GUI Style:", None))


class SettingsWindow(QDialog):
    def __init__(self):
        super().__init__(None, Qt.WindowSystemMenuHint |
                         Qt.WindowTitleHint | Qt.WindowCloseButtonHint)

        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("Dialog")

        if sys.platform == "win32":
            self.setFixedSize(300, 240)
        else:
            self.setFixedSize(370, 240)

        self.setModal(True)
        icon = QIcon()
        icon.addPixmap(QPixmap(
            str(resource_path("bin/icon.ico"))), QIcon.Normal, QIcon.Off)
        self.setWindowIcon(icon)

        # Buttonbox
        self.buttonBox = QDialogButtonBox(self)

        if sys.platform == "win32":
            self.buttonBox.setFixedSize(280, 30)
        else:
            self.buttonBox.setFixedSize(350, 30)

        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")

        self.formLayoutWidget = QGridLayout(self)
        self.formLayoutWidget.setObjectName("formLayoutWidget")

        self.comboBoxLayout = QGridLayout()
        self.comboBoxLayout.setVerticalSpacing(10)
        self.comboBoxLayout.setObjectName("comboBoxLayout")

        # protect codes
        self.protectCodes = QCheckBox()
        self.protectCodes.setObjectName("protectCodes")
        self.protectCodes.setText("Protect Game (Prevent user codes)")
        self.comboBoxLayout.addWidget(self.protectCodes, 1, 0, 1, 1)

        # encrypt codes
        self.encryptCodes = QCheckBox()
        self.encryptCodes.setObjectName("encryptCodes")
        self.encryptCodes.setText("Encrypt codes")
        self.comboBoxLayout.addWidget(self.encryptCodes, 2, 0, 1, 1)

        # optimize codes
        self.optimizeCodes = QCheckBox()
        self.optimizeCodes.setObjectName("optimizeCodes")
        self.optimizeCodes.setText("Optimize codes")
        self.optimizeCodes.setChecked(True)
        self.comboBoxLayout.addWidget(self.optimizeCodes, 3, 0, 1, 1)

        # Codehook Address Label
        self.codehookLabel = QLabel()
        self.codehookLabel.setObjectName("codehookLabel")
        self.comboBoxLayout.addWidget(self.codehookLabel, 4, 0, 1, 1)

        # Codehook Address Textbox
        self.codehookLineEdit = QLineEdit()
        self.codehookLineEdit.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.codehookLineEdit.sizePolicy().hasHeightForWidth())
        self.codehookLineEdit.setSizePolicy(sizePolicy)
        self.codehookLineEdit.setMinimumSize(QSize(79, 23))
        self.codehookLineEdit.setMaximumSize(QSize(79, 23))
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(12)
        font.setWeight(42)
        self.codehookLineEdit.setFont(font)
        self.codehookLineEdit.setText("")
        self.codehookLineEdit.setMaxLength(8)
        self.codehookLineEdit.setAlignment(
            Qt.AlignLeading | Qt.AlignCenter | Qt.AlignVCenter)
        self.codehookLineEdit.setObjectName("codehookLineEdit")
        self.comboBoxLayout.addWidget(self.codehookLineEdit, 4, 1, 1, 1)

        # kernelHook Address Label
        self.kernelHookLabel = QLabel()
        self.kernelHookLabel.setObjectName("kernelHookLabel")
        self.comboBoxLayout.addWidget(self.kernelHookLabel, 5, 0, 1, 1)

        # kernelHook Address Textbox
        self.kernelHookLineEdit = QLineEdit()
        self.kernelHookLineEdit.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.kernelHookLineEdit.sizePolicy().hasHeightForWidth())
        self.kernelHookLineEdit.setSizePolicy(sizePolicy)
        self.kernelHookLineEdit.setMinimumSize(QSize(79, 23))
        self.kernelHookLineEdit.setMaximumSize(QSize(79, 23))
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(12)
        font.setWeight(42)
        self.kernelHookLineEdit.setFont(font)
        self.kernelHookLineEdit.setText("")
        self.kernelHookLineEdit.setMaxLength(8)
        self.kernelHookLineEdit.setAlignment(
            Qt.AlignLeading | Qt.AlignCenter | Qt.AlignVCenter)
        self.kernelHookLineEdit.setObjectName("kernelHookLineEdit")
        self.comboBoxLayout.addWidget(self.kernelHookLineEdit, 5, 1, 1, 1)

        # verbosity label
        self.verbosityLabel = QLabel()
        self.verbosityLabel.setObjectName("verbosityLabel")
        self.comboBoxLayout.addWidget(self.verbosityLabel, 6, 0, 1, 1)

        # verbosity box
        self.verbositySelect = QComboBox()
        self.verbositySelect.addItems(["1", "2", "3", "0"])
        self.verbositySelect.setObjectName("verbositySelect")
        self.comboBoxLayout.addWidget(self.verbositySelect, 6, 1, 1, 1)

        self.formLayoutWidget.addLayout(self.comboBoxLayout, 0, 0, 1, 1)
        self.formLayoutWidget.addWidget(self.buttonBox, 1, 0, 1, 1)

        self.set_edit_fields()
        self.retranslateUi()

        self.buttonBox.accepted.connect(self.accept)
        QMetaObject.connectSlotsByName(self)

    def set_edit_fields(self):
        self.protectCodes.setEnabled(True)
        self.encryptCodes.setEnabled(True)
        self.optimizeCodes.setEnabled(True)
        self.codehookLineEdit.setEnabled(True)
        self.kernelHookLineEdit.setEnabled(True)
        self.verbositySelect.setEnabled(True)

    def retranslateUi(self):
        self.setWindowTitle(QApplication.translate(
            "Dialog", "Advanced Settings", None))
        self.codehookLabel.setText(QApplication.translate(
            "Dialog", "Codehook Address:", None))
        self.kernelHookLabel.setText(QApplication.translate(
            "Dialog", "Kernel Init Address:", None))
        self.verbosityLabel.setText(
            QApplication.translate("Dialog", "Verbosity:", None))
