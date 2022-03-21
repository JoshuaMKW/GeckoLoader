from PySide6.QtGui import QIcon, QPalette, QFont, QCloseEvent, QPixmap, QColor, QFontMetricsF, QAction
from PySide6.QtCore import Qt, QSize, QRect, QMetaObject
from PySide6.QtWidgets import (QApplication, QComboBox, QWidget,
                               QGridLayout, QLabel, QMessageBox, QPushButton, QFrame, QPlainTextEdit, QMenuBar, QMenu, QStatusBar, QMainWindow,
                               QLineEdit, QSizePolicy)

from geckoloader.fileutils import resource_path


class MainWindow(QMainWindow):
    def __init__(self, version: str):
        super().__init__()

        self._job_active = False
        self.apiRevision = version
        self.setup_ui()

        self.LightTheme = self.palette()

        self.DarkTheme = QPalette()
        self.DarkTheme.setColor(QPalette.Window, QColor(53, 53, 53))
        self.DarkTheme.setColor(QPalette.WindowText, Qt.white)
        self.DarkTheme.setColor(QPalette.Base, QColor(25, 25, 25))
        self.DarkTheme.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        self.DarkTheme.setColor(QPalette.ToolTipBase, Qt.black)
        self.DarkTheme.setColor(QPalette.ToolTipText, Qt.white)
        self.DarkTheme.setColor(QPalette.Text, Qt.white)
        self.DarkTheme.setColor(QPalette.Button, QColor(53, 53, 53))
        self.DarkTheme.setColor(QPalette.ButtonText, Qt.white)
        self.DarkTheme.setColor(QPalette.BrightText, Qt.red)
        self.DarkTheme.setColor(QPalette.Link, QColor(42, 130, 218))
        self.DarkTheme.setColor(QPalette.Highlight, QColor(42, 130, 218))
        self.DarkTheme.setColor(QPalette.HighlightedText, Qt.black)

    def set_job_activity(self, active: bool):
        self._job_active = active

    def close_event(self, event: QCloseEvent):
        if self._job_active:
            reply = QMessageBox(self)
            reply.setWindowTitle("Active job")
            reply.setText("GeckoLoader is busy!")
            reply.setInformativeText("Exiting is disabled")
            reply.setIcon(QMessageBox.Warning)
            reply.setStandardButtons(QMessageBox.Ok)
            reply.setDefaultButton(QMessageBox.Ok)
            reply.exec_()
            event.ignore()
        else:
            event.accept()

    def setup_ui(self):
        self.setObjectName("MainWindow")
        self.setWindowModality(Qt.NonModal)
        self.setEnabled(True)
        self.setFixedSize(550, 680)
        font = QFont()
        font.setFamily("Helvetica")
        font.setPointSize(10)
        font.setWeight(42)
        self.setFont(font)
        icon = QIcon()
        icon.addPixmap(QPixmap(str(resource_path("bin/icon.ico"))),
                       QIcon.Normal, QIcon.Off)
        self.setWindowIcon(icon)

        # Top level widget
        self.centerWidget = QWidget(self)
        self.centerWidget.setObjectName("centerWidget")

        self.gridLayout = QGridLayout(self.centerWidget)
        self.gridLayout.setVerticalSpacing(0)
        self.gridLayout.setObjectName("gridLayout")

        # Layout for file paths and open boxes
        self.filesLayout = QGridLayout()
        self.filesLayout.setHorizontalSpacing(0)
        self.filesLayout.setObjectName("filesLayout")

        self.dolLayout = QGridLayout()
        self.dolLayout.setHorizontalSpacing(0)
        self.dolLayout.setObjectName("dolLayout")

        # Layout for folder path
        self.gctLayout = QGridLayout()
        self.gctLayout.setHorizontalSpacing(0)
        self.gctLayout.setVerticalSpacing(5)
        self.gctLayout.setObjectName("gctLayout")

        self.destLayout = QGridLayout()
        self.dolLayout.setHorizontalSpacing(0)
        self.dolLayout.setObjectName("dolLayout")

        # Files label
        self.filesLabel = QLabel(self.centerWidget)
        self.filesLabel.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.filesLabel.sizePolicy().hasHeightForWidth())
        self.filesLabel.setSizePolicy(sizePolicy)
        self.filesLabel.setMinimumSize(QSize(80, 30))
        self.filesLabel.setMaximumSize(QSize(16777215, 30))
        font = QFont("Helvetica")
        font.setPointSize(21)
        font.setWeight(82)
        font.setBold(True)
        self.filesLabel.setFont(font)
        self.filesLabel.setTextFormat(Qt.PlainText)
        self.filesLabel.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.filesLabel.setObjectName("filesLabel")

        # Dol button to open file
        self.dolButton = QPushButton(self.centerWidget)
        self.dolButton.setMinimumSize(QSize(100, 26))
        self.dolButton.setMaximumSize(QSize(100, 26))
        font = QFont("Helvetica")
        font.setPointSize(11)
        self.dolButton.setFont(font)
        self.dolButton.setCheckable(False)
        self.dolButton.setChecked(False)
        self.dolButton.setAutoDefault(True)
        self.dolButton.setDefault(False)
        self.dolButton.setFlat(False)
        self.dolButton.setObjectName("dolButton")
        self.dolLayout.addWidget(self.dolButton, 1, 0, 1, 1)

        # Dol path textbox
        self.dolTextBox = QLineEdit(self.centerWidget)
        self.dolTextBox.setEnabled(False)
        self.dolTextBox.setMinimumSize(QSize(200, 24))
        self.dolTextBox.setMaximumSize(QSize(16777215, 24))
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(10)
        font.setWeight(42)
        self.dolTextBox.setFont(font)
        self.dolTextBox.setText("")
        self.dolTextBox.setMaxLength(255)
        self.dolTextBox.setFrame(True)
        self.dolTextBox.setAlignment(
            Qt.AlignLeading | Qt.AlignCenter | Qt.AlignVCenter)
        self.dolTextBox.setObjectName("dolTextBox")
        self.dolLayout.addWidget(self.dolTextBox, 1, 1, 1, 1)

        # horizontal separater codes
        self.horiSepFiles = QFrame(self.centerWidget)
        self.horiSepFiles.setMinimumSize(QSize(474, 30))
        self.horiSepFiles.setContentsMargins(20, 0, 20, 0)
        self.horiSepFiles.setFrameShape(QFrame.HLine)
        self.horiSepFiles.setFrameShadow(QFrame.Sunken)
        self.horiSepFiles.setObjectName("horiSepFiles")

        # gctFile button to open file
        self.gctFileButton = QPushButton(self.centerWidget)
        self.gctFileButton.setMinimumSize(QSize(100, 26))
        self.gctFileButton.setMaximumSize(QSize(100, 26))
        font = QFont("Helvetica")
        font.setPointSize(10)
        self.gctFileButton.setFont(font)
        self.gctFileButton.setCheckable(False)
        self.gctFileButton.setChecked(False)
        self.gctFileButton.setAutoDefault(True)
        self.gctFileButton.setDefault(False)
        self.gctFileButton.setFlat(False)
        self.gctFileButton.setObjectName("gctFileButton")
        self.gctLayout.addWidget(self.gctFileButton, 0, 0, 1, 1)

        # gctFile path textbox
        self.gctFileTextBox = QLineEdit(self.centerWidget)
        self.gctFileTextBox.setEnabled(False)
        self.gctFileTextBox.setMinimumSize(QSize(200, 24))
        self.gctFileTextBox.setMaximumSize(QSize(16777215, 24))
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(10)
        font.setWeight(42)
        self.gctFileTextBox.setFont(font)
        self.gctFileTextBox.setText("")
        self.gctFileTextBox.setMaxLength(255)
        self.gctFileTextBox.setFrame(True)
        self.gctFileTextBox.setAlignment(
            Qt.AlignLeading | Qt.AlignCenter | Qt.AlignVCenter)
        self.gctFileTextBox.setObjectName("gctFileTextBox")
        self.gctLayout.addWidget(self.gctFileTextBox, 0, 1, 1, 1)

        # --or-- Label
        self.orFolderLabel = QLabel(self.centerWidget)
        self.orFolderLabel.setEnabled(False)
        self.orFolderLabel.setMinimumSize(QSize(80, 8))
        self.orFolderLabel.setMaximumSize(QSize(16777215, 8))
        font = QFont("Helvetica")
        font.setPointSize(8)
        font.setWeight(82)
        font.setBold(True)
        self.orFolderLabel.setFont(font)
        self.orFolderLabel.setTextFormat(Qt.PlainText)
        self.orFolderLabel.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.orFolderLabel.setObjectName("orFolderLabel")
        self.gctLayout.addWidget(self.orFolderLabel, 1, 0, 1, 2)

        # gctFolder button to open file
        self.gctFolderButton = QPushButton(self.centerWidget)
        self.gctFolderButton.setMinimumSize(QSize(100, 26))
        self.gctFolderButton.setMaximumSize(QSize(100, 26))
        font = QFont("Helvetica")
        font.setPointSize(10)
        self.gctFolderButton.setFont(font)
        self.gctFolderButton.setCheckable(False)
        self.gctFolderButton.setChecked(False)
        self.gctFolderButton.setAutoDefault(True)
        self.gctFolderButton.setDefault(False)
        self.gctFolderButton.setFlat(False)
        self.gctFolderButton.setObjectName("gctFolderButton")
        self.gctLayout.addWidget(self.gctFolderButton, 2, 0, 1, 1)

        # gctFolder path textbox
        self.gctFolderTextBox = QLineEdit(self.centerWidget)
        self.gctFolderTextBox.setEnabled(False)
        self.gctFolderTextBox.setMinimumSize(QSize(200, 24))
        self.gctFolderTextBox.setMaximumSize(QSize(16777215, 24))
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(10)
        font.setWeight(42)
        self.gctFolderTextBox.setFont(font)
        self.gctFolderTextBox.setText("")
        self.gctFolderTextBox.setMaxLength(255)
        self.gctFolderTextBox.setFrame(True)
        self.gctFolderTextBox.setAlignment(
            Qt.AlignLeading | Qt.AlignCenter | Qt.AlignVCenter)
        self.gctFolderTextBox.setObjectName("gctFolderTextBox")
        self.gctLayout.addWidget(self.gctFolderTextBox, 2, 1, 1, 1)

        # horizontal separater dest
        self.horiSepDest = QFrame(self.centerWidget)
        self.horiSepDest.setMinimumSize(QSize(474, 30))
        self.horiSepDest.setContentsMargins(20, 0, 20, 0)
        self.horiSepDest.setFrameShape(QFrame.HLine)
        self.horiSepDest.setFrameShadow(QFrame.Sunken)
        self.horiSepDest.setObjectName("horiSepDest")

        # Dest button to open file
        self.destButton = QPushButton(self.centerWidget)
        self.destButton.setMinimumSize(QSize(100, 26))
        self.destButton.setMaximumSize(QSize(100, 26))
        font = QFont("Helvetica")
        font.setPointSize(11)
        self.destButton.setFont(font)
        self.destButton.setCheckable(False)
        self.destButton.setChecked(False)
        self.destButton.setAutoDefault(True)
        self.destButton.setDefault(False)
        self.destButton.setFlat(False)
        self.destButton.setObjectName("destButton")
        self.destLayout.addWidget(self.destButton, 0, 0, 1, 1)

        # Dest path textbox
        self.destTextBox = QLineEdit(self.centerWidget)
        self.destTextBox.setEnabled(False)
        self.destTextBox.setMinimumSize(QSize(200, 24))
        self.destTextBox.setMaximumSize(QSize(16777215, 24))
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(10)
        font.setWeight(42)
        self.destTextBox.setFont(font)
        self.destTextBox.setText("")
        self.destTextBox.setMaxLength(255)
        self.destTextBox.setFrame(True)
        self.destTextBox.setAlignment(
            Qt.AlignLeading | Qt.AlignCenter | Qt.AlignVCenter)
        self.destTextBox.setObjectName("destTextBox")
        self.destLayout.addWidget(self.destTextBox, 0, 1, 1, 1)

        self.filesLayout.addLayout(self.dolLayout, 0, 0, 1, 1)
        self.filesLayout.addWidget(self.horiSepFiles, 1, 0, 1, 1)
        self.filesLayout.addLayout(self.gctLayout, 2, 0, 1, 1)
        self.filesLayout.addWidget(self.horiSepDest, 3, 0, 1, 1)
        self.filesLayout.addLayout(self.destLayout, 4, 0, 1, 1)

        # Options Layout
        self.optionsLayout = QGridLayout()
        self.optionsLayout.setHorizontalSpacing(20)
        self.optionsLayout.setObjectName("optionsLayout")

        # Options Label
        self.optionsLabel = QLabel(self.centerWidget)
        self.optionsLabel.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.optionsLabel.sizePolicy().hasHeightForWidth())
        self.optionsLabel.setSizePolicy(sizePolicy)
        self.optionsLabel.setMinimumSize(QSize(79, 23))
        self.optionsLabel.setMaximumSize(QSize(16777215, 23))
        font = QFont("Helvetica")
        font.setPointSize(18)
        font.setWeight(82)
        font.setBold(True)
        self.optionsLabel.setFont(font)
        self.optionsLabel.setTextFormat(Qt.PlainText)
        self.optionsLabel.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.optionsLabel.setObjectName("optionsLabel")
        self.optionsLayout.addWidget(self.optionsLabel, 0, 0, 1, 4)

        # Allocation Label
        self.allocLabel = QLabel(self.centerWidget)
        self.allocLabel.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.allocLabel.sizePolicy().hasHeightForWidth())
        self.allocLabel.setSizePolicy(sizePolicy)
        self.allocLabel.setMinimumSize(QSize(79, 23))
        self.allocLabel.setMaximumSize(QSize(16777215, 23))
        self.allocLabel.setTextFormat(Qt.PlainText)
        self.allocLabel.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.allocLabel.setObjectName("allocLabel")
        self.optionsLayout.addWidget(self.allocLabel, 1, 0, 1, 1)

        # Allocation Textbox
        self.allocLineEdit = QLineEdit(self.centerWidget)
        self.allocLineEdit.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.allocLineEdit.sizePolicy().hasHeightForWidth())
        self.allocLineEdit.setSizePolicy(sizePolicy)
        self.allocLineEdit.setMinimumSize(QSize(79, 23))
        self.allocLineEdit.setMaximumSize(QSize(79, 23))
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(12)
        font.setWeight(42)
        self.allocLineEdit.setFont(font)
        self.allocLineEdit.setText("")
        self.allocLineEdit.setMaxLength(6)
        self.allocLineEdit.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.allocLineEdit.setObjectName("allocLineEdit")
        self.optionsLayout.addWidget(self.allocLineEdit, 2, 0, 1, 1)

        # handlerType label
        self.handlerTypeLabel = QLabel(self.centerWidget)
        self.handlerTypeLabel.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.handlerTypeLabel.sizePolicy().hasHeightForWidth())
        self.handlerTypeLabel.setSizePolicy(sizePolicy)
        self.handlerTypeLabel.setMinimumSize(QSize(79, 23))
        self.handlerTypeLabel.setMaximumSize(QSize(16777215, 23))
        self.handlerTypeLabel.setTextFormat(Qt.PlainText)
        self.handlerTypeLabel.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.handlerTypeLabel.setObjectName("handlerTypeLabel")
        self.optionsLayout.addWidget(self.handlerTypeLabel, 1, 1, 1, 1)

        # handlerType selection
        self.handlerTypeSelect = QComboBox(self.centerWidget)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.allocLabel.sizePolicy().hasHeightForWidth())
        self.handlerTypeSelect.setSizePolicy(sizePolicy)
        self.handlerTypeSelect.setMinimumSize(QSize(79, 23))
        self.handlerTypeSelect.setMaximumSize(QSize(79, 23))
        self.handlerTypeSelect.setObjectName("handlerTypeSelect")
        self.handlerTypeSelect.addItems(["FULL", "MINI"])
        self.optionsLayout.addWidget(self.handlerTypeSelect, 2, 1, 1, 1)

        # hookType label
        self.hookTypeLabel = QLabel(self.centerWidget)
        self.hookTypeLabel.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.hookTypeLabel.sizePolicy().hasHeightForWidth())
        self.hookTypeLabel.setSizePolicy(sizePolicy)
        self.hookTypeLabel.setMinimumSize(QSize(79, 23))
        self.hookTypeLabel.setMaximumSize(QSize(16777215, 23))
        self.hookTypeLabel.setTextFormat(Qt.PlainText)
        self.hookTypeLabel.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.hookTypeLabel.setObjectName("hookTypeLabel")
        self.optionsLayout.addWidget(self.hookTypeLabel, 1, 2, 1, 1)

        # hookType selection
        self.hookTypeSelect = QComboBox(self.centerWidget)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.allocLabel.sizePolicy().hasHeightForWidth())
        self.hookTypeSelect.setSizePolicy(sizePolicy)
        self.hookTypeSelect.setMinimumSize(QSize(79, 23))
        self.hookTypeSelect.setMaximumSize(QSize(79, 23))
        self.hookTypeSelect.setObjectName("hookTypeSelect")
        self.hookTypeSelect.addItems(["VI", "GX", "PAD"])
        self.optionsLayout.addWidget(self.hookTypeSelect, 2, 2, 1, 1)

        # txtCodesInclude label
        self.txtCodesIncludeLabel = QLabel(self.centerWidget)
        self.txtCodesIncludeLabel.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.txtCodesIncludeLabel.sizePolicy().hasHeightForWidth())
        self.txtCodesIncludeLabel.setSizePolicy(sizePolicy)
        self.txtCodesIncludeLabel.setMinimumSize(QSize(79, 23))
        self.txtCodesIncludeLabel.setMaximumSize(QSize(16777215, 23))
        self.txtCodesIncludeLabel.setTextFormat(Qt.PlainText)
        self.txtCodesIncludeLabel.setAlignment(
            Qt.AlignCenter | Qt.AlignVCenter)
        self.txtCodesIncludeLabel.setObjectName("txtCodesIncludeLabel")
        self.optionsLayout.addWidget(self.txtCodesIncludeLabel, 1, 3, 1, 1)

        # txtCodesInclude selection
        self.txtCodesIncludeSelect = QComboBox(self.centerWidget)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.allocLabel.sizePolicy().hasHeightForWidth())
        self.txtCodesIncludeSelect.setSizePolicy(sizePolicy)
        self.txtCodesIncludeSelect.setMinimumSize(QSize(79, 23))
        self.txtCodesIncludeSelect.setMaximumSize(QSize(79, 23))
        self.txtCodesIncludeSelect.setObjectName("txtCodesIncludeSelect")
        self.txtCodesIncludeSelect.addItems(["ACTIVE", "ALL"])
        self.optionsLayout.addWidget(self.txtCodesIncludeSelect, 2, 3, 1, 1)

        # horizontal separater options
        self.horiSepOptions = QFrame(self.centerWidget)
        self.horiSepOptions.setMinimumSize(QSize(300, 30))
        self.horiSepOptions.setContentsMargins(20, 0, 20, 0)
        self.horiSepOptions.setFrameShape(QFrame.HLine)
        self.horiSepOptions.setFrameShadow(QFrame.Sunken)
        self.horiSepOptions.setObjectName("horiSepOptions")
        self.optionsLayout.addWidget(self.horiSepOptions, 3, 0, 1, 4)

        # Advanced options button
        self.exOptionsButton = QPushButton(self.centerWidget)
        font = QFont("Helvetica")
        font.setPointSize(13)
        self.exOptionsButton.setFont(font)
        self.exOptionsButton.setCheckable(False)
        self.exOptionsButton.setChecked(False)
        self.exOptionsButton.setAutoDefault(True)
        self.exOptionsButton.setDefault(False)
        self.exOptionsButton.setFlat(False)
        self.exOptionsButton.setDisabled(True)
        self.exOptionsButton.setObjectName("exOptionsButton")
        self.optionsLayout.addWidget(self.exOptionsButton, 4, 0, 1, 4)

        # horizontal separater 1
        self.horiSepA = QFrame(self.centerWidget)
        self.horiSepA.setMinimumSize(QSize(470, 30))
        self.horiSepA.setFrameShape(QFrame.HLine)
        self.horiSepA.setFrameShadow(QFrame.Sunken)
        self.horiSepA.setObjectName("horiSepA")

        # horizontal separater 2
        self.horiSepB = QFrame(self.centerWidget)
        self.horiSepB.setMinimumSize(QSize(470, 30))
        self.horiSepB.setFrameShape(QFrame.HLine)
        self.horiSepB.setFrameShadow(QFrame.Sunken)
        self.horiSepB.setObjectName("horiSepB")

        # response panel
        self.responses = QPlainTextEdit(self.centerWidget)
        self.responses.setEnabled(True)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.responses.sizePolicy().hasHeightForWidth())
        self.responses.setSizePolicy(sizePolicy)
        self.responses.setMinimumSize(QSize(474, 180))
        self.responses.setMaximumSize(QSize(16777215, 180))
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(8)
        font.setWeight(42)
        fontMetrics = QFontMetricsF(font)
        spaceWidth = fontMetrics.width(' ')
        self.responses.setFont(font)
        self.responses.setPlainText("")
        self.responses.setTabStopDistance(spaceWidth * 4)
        self.responses.setReadOnly(True)
        self.responses.setObjectName("responses")

        # Compile button
        self.compileButton = QPushButton(self.centerWidget)
        font = QFont("Helvetica")
        font.setPointSize(34)
        self.compileButton.setFont(font)
        self.compileButton.setCheckable(False)
        self.compileButton.setChecked(False)
        self.compileButton.setAutoDefault(True)
        self.compileButton.setDefault(False)
        self.compileButton.setFlat(False)
        self.compileButton.setDisabled(True)
        self.compileButton.setObjectName("compileButton")

        self.gridLayout.addWidget(self.filesLabel, 0, 0, 1, 1)
        self.gridLayout.addLayout(self.filesLayout, 1, 0, 1, 1)
        self.gridLayout.addWidget(self.horiSepA, 2, 0, 1, 1)
        self.gridLayout.addLayout(self.optionsLayout, 3, 0, 1, 1)
        self.gridLayout.addWidget(self.horiSepB, 4, 0, 1, 1)
        self.gridLayout.addWidget(self.responses, 5, 0, 1, 1)
        self.gridLayout.addWidget(self.compileButton, 6, 0, 1, 1)

        self.setCentralWidget(self.centerWidget)

        # Toolbar
        self.menubar = QMenuBar(self)
        self.menubar.setGeometry(QRect(0, 0, 470, 22))
        self.menubar.setObjectName("menubar")

        self.menuFile = QMenu(self.menubar)
        font = QFont()
        font.setFamily("Helvetica")
        self.menuFile.setFont(font)
        self.menuFile.setObjectName("menuFile")

        self.menuEdit = QMenu(self.menubar)
        font = QFont()
        font.setFamily("Helvetica")
        self.menuEdit.setFont(font)
        self.menuEdit.setObjectName("menuEdit")

        self.menuHelp = QMenu(self.menubar)
        font = QFont()
        font.setFamily("Helvetica")
        self.menuHelp.setFont(font)
        self.menuHelp.setObjectName("menuHelp")

        self.setMenuBar(self.menubar)

        self.actionOpen = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionOpen.setFont(font)
        self.actionOpen.setObjectName("actionOpen")

        self.actionClose = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionClose.setFont(font)
        self.actionClose.setObjectName("actionClose")

        self.actionSave = QAction(self)
        self.actionSave.setEnabled(False)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionSave.setFont(font)
        self.actionSave.setObjectName("actionSave")

        self.actionSave_As = QAction(self)
        self.actionSave_As.setEnabled(False)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionSave_As.setFont(font)
        self.actionSave_As.setObjectName("actionSave_As")

        self.actionUndo = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionUndo.setFont(font)
        self.actionUndo.setMenuRole(QAction.TextHeuristicRole)
        self.actionUndo.setObjectName("actionUndo")
        self.actionRedo = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionRedo.setFont(font)
        self.actionRedo.setObjectName("actionRedo")
        self.actionCut = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionCut.setFont(font)
        self.actionCut.setObjectName("actionCut")
        self.actionCopy = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionCopy.setFont(font)
        self.actionCopy.setObjectName("actionCopy")
        self.actionPaste = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionPaste.setFont(font)
        self.actionPaste.setObjectName("actionPaste")
        self.actionDelete = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionDelete.setFont(font)
        self.actionDelete.setObjectName("actionDelete")
        self.actionSelect_All = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionSelect_All.setFont(font)
        self.actionSelect_All.setObjectName("actionSelect_All")
        self.actionPreferences = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionPreferences.setFont(font)
        self.actionPreferences.setMenuRole(QAction.PreferencesRole)
        self.actionPreferences.setObjectName("actionPreferences")

        self.actionAbout_GeckoLoader = QAction(self)
        font = QFont()
        font.setFamily("Helvetica")
        self.actionAbout_GeckoLoader.setFont(font)
        self.actionAbout_GeckoLoader.setMenuRole(QAction.AboutRole)
        self.actionAbout_GeckoLoader.setObjectName("actionAbout_GeckoLoader")

        self.actionAbout_Qt = QAction(self)
        self.actionAbout_Qt.setStatusTip("")
        font = QFont()
        font.setFamily("Helvetica")
        self.actionAbout_Qt.setFont(font)
        self.actionAbout_Qt.setMenuRole(QAction.AboutQtRole)
        self.actionAbout_Qt.setObjectName("actionAbout_Qt")

        self.actionCheck_Update = QAction(self)
        self.actionCheck_Update.setStatusTip("")
        font = QFont()
        font.setFamily("Helvetica")
        self.actionCheck_Update.setFont(font)
        self.actionCheck_Update.setObjectName("actionCheck_Update")

        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addAction(self.actionClose)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionSave_As)

        self.menuEdit.addAction(self.actionPreferences)

        self.menuHelp.addAction(self.actionAbout_GeckoLoader)
        self.menuHelp.addAction(self.actionAbout_Qt)
        self.menuHelp.addAction(self.actionCheck_Update)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())

        # Statusbar
        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)

        self.retranslate_ui()
        self.set_edit_fields()

        QMetaObject.connectSlotsByName(self)

    def set_edit_fields(self):
        self.filesLabel.setEnabled(True)
        self.dolTextBox.setEnabled(True)
        self.destTextBox.setEnabled(True)
        self.optionsLabel.setEnabled(True)
        self.allocLabel.setEnabled(True)
        self.allocLineEdit.setEnabled(True)
        self.handlerTypeLabel.setEnabled(True)
        self.handlerTypeSelect.setEnabled(True)
        self.hookTypeLabel.setEnabled(True)
        self.hookTypeSelect.setEnabled(True)
        self.txtCodesIncludeLabel.setEnabled(True)
        self.txtCodesIncludeSelect.setEnabled(True)
        self.exOptionsButton.setEnabled(True)
        self.actionSave.setEnabled(True)
        self.actionSave_As.setEnabled(True)

        self._lstrip_textboxes()

        if self.gctFileTextBox.text() != "":
            self.gctFileTextBox.setEnabled(True)
            self.gctFolderTextBox.setDisabled(True)
        elif self.gctFolderTextBox.text() != "":
            self.gctFileTextBox.setDisabled(True)
            self.gctFolderTextBox.setEnabled(True)
        else:
            self.gctFileTextBox.setEnabled(True)
            self.gctFolderTextBox.setEnabled(True)

        if self.dolTextBox.text().lower().endswith(".dol") and len(self.dolTextBox.text()) > 4:
            self.compileButton.setEnabled(
                self.gctFileTextBox.text() != "" or self.gctFolderTextBox.text() != "")
        else:
            self.compileButton.setDisabled(True)

    def retranslate_ui(self):
        self.setWindowTitle(QApplication.translate(
            "MainWindow", f"GeckoLoader {self.apiRevision} - untitled", None))
        self.menuFile.setTitle(
            QApplication.translate("MainWindow", "&File", None))
        self.menuEdit.setTitle(
            QApplication.translate("MainWindow", "&Edit", None))
        self.menuHelp.setTitle(
            QApplication.translate("MainWindow", "&Help", None))
        self.actionOpen.setText(QApplication.translate(
            "MainWindow", "&Open Session...", None))
        self.actionOpen.setStatusTip(QApplication.translate(
            "MainWindow", "Open a session", None))
        self.actionOpen.setShortcut(
            QApplication.translate("MainWindow", "Ctrl+O", None))
        self.actionClose.setText(QApplication.translate(
            "MainWindow", "&Close Session...", None))
        self.actionClose.setStatusTip(QApplication.translate(
            "MainWindow", "Close the current session", None))
        self.actionClose.setShortcut(QApplication.translate(
            "MainWindow", "Ctrl+Shift+C", None))
        self.actionSave.setText(QApplication.translate(
            "MainWindow", "&Save Session", None))
        self.actionSave.setStatusTip(QApplication.translate(
            "MainWindow", "Save the current session", None))
        self.actionSave.setShortcut(
            QApplication.translate("MainWindow", "Ctrl+S", None))
        self.actionSave_As.setText(QApplication.translate(
            "MainWindow", "&Save Session As...", None))
        self.actionSave_As.setStatusTip(QApplication.translate(
            "MainWindow", "Save the current session to the specified location", None))
        self.actionSave_As.setShortcut(
            QApplication.translate("MainWindow", "Ctrl+Shift+S", None))
        self.actionUndo.setText(
            QApplication.translate("MainWindow", "Undo", None))
        self.actionUndo.setStatusTip(QApplication.translate(
            "MainWindow", "Undo the last action", None))
        self.actionUndo.setShortcut(
            QApplication.translate("MainWindow", "Ctrl+Z", None))
        self.actionRedo.setText(
            QApplication.translate("MainWindow", "Redo", None))
        self.actionRedo.setStatusTip(QApplication.translate(
            "MainWindow", "Redo the last action", None))
        self.actionRedo.setShortcut(QApplication.translate(
            "MainWindow", "Ctrl+Shift+Z", None))
        self.actionCut.setText(
            QApplication.translate("MainWindow", "Cut", None))
        self.actionCut.setStatusTip(QApplication.translate(
            "MainWindow", "Cuts the selected text and places it on the clipboard", None))
        self.actionCut.setShortcut(
            QApplication.translate("MainWindow", "Ctrl+X", None))
        self.actionCopy.setText(
            QApplication.translate("MainWindow", "Copy", None))
        self.actionCopy.setStatusTip(QApplication.translate(
            "MainWindow", "Copies the selected text and places it on the clipboard", None))
        self.actionCopy.setShortcut(
            QApplication.translate("MainWindow", "Ctrl+C", None))
        self.actionPaste.setText(
            QApplication.translate("MainWindow", "Paste", None))
        self.actionPaste.setStatusTip(QApplication.translate(
            "MainWindow", "Paste the contents of the clipboard", None))
        self.actionPaste.setShortcut(
            QApplication.translate("MainWindow", "Ctrl+V", None))
        self.actionDelete.setText(
            QApplication.translate("MainWindow", "Delete", None))
        self.actionDelete.setStatusTip(QApplication.translate(
            "MainWindow", "Deletes the selected text", None))
        self.actionSelect_All.setText(
            QApplication.translate("MainWindow", "Select All", None))
        self.actionSelect_All.setStatusTip(QApplication.translate(
            "MainWindow", "Select all of the text", None))
        self.actionSelect_All.setShortcut(
            QApplication.translate("MainWindow", "Ctrl+A", None))
        self.actionPreferences.setText(QApplication.translate(
            "MainWindow", "&Preferences...", None))
        self.actionPreferences.setStatusTip(QApplication.translate(
            "MainWindow", "Open the application preferences dialog", None))
        self.actionAbout_GeckoLoader.setText(QApplication.translate(
            "MainWindow", "About &GeckoLoader...", None))
        self.actionAbout_Qt.setText(QApplication.translate(
            "MainWindow", "About &Qt...", None))
        self.actionCheck_Update.setText(
            QApplication.translate("MainWindow", "&Check Update", None))

        self.filesLabel.setText(
            QApplication.translate("MainWindow", "Files", None))

        self.dolButton.setText(QApplication.translate(
            "MainWindow", "Open DOL", None))
        self.gctFileButton.setText(QApplication.translate(
            "MainWindow", "Open Codes", None))
        self.orFolderLabel.setText(QApplication.translate(
            "MainWindow", "-"*40 + "OR" + "-"*40, None))
        self.gctFolderButton.setText(
            QApplication.translate("MainWindow", "Open Folder", None))
        self.destButton.setText(QApplication.translate(
            "MainWindow", "Destination", None))

        self.optionsLabel.setText(
            QApplication.translate("MainWindow", "Options", None))

        self.allocLabel.setText(QApplication.translate(
            "MainWindow", "Allocation", None))
        self.allocLineEdit.setPlaceholderText(
            QApplication.translate("MainWindow", "AUTO", None))

        self.handlerTypeLabel.setText(
            QApplication.translate("MainWindow", "Codehandler", None))
        self.handlerTypeSelect.setItemText(
            0, QApplication.translate("Dialog", "FULL", None))
        self.handlerTypeSelect.setItemText(
            1, QApplication.translate("Dialog", "MINI", None))

        self.hookTypeLabel.setText(
            QApplication.translate("MainWindow", "Code Hook", None))
        self.hookTypeSelect.setItemText(
            0, QApplication.translate("Dialog", "VI", None))
        self.hookTypeSelect.setItemText(
            1, QApplication.translate("Dialog", "GX", None))
        self.hookTypeSelect.setItemText(
            2, QApplication.translate("Dialog", "PAD", None))

        self.txtCodesIncludeLabel.setText(
            QApplication.translate("MainWindow", "Include Codes", None))
        self.txtCodesIncludeSelect.setItemText(
            0, QApplication.translate("Dialog", "ACTIVE", None))
        self.txtCodesIncludeSelect.setItemText(
            1, QApplication.translate("Dialog", "ALL", None))

        self.exOptionsButton.setText(QApplication.translate(
            "MainWindow", "Advanced Settings", None))

        self.compileButton.setText(
            QApplication.translate("MainWindow", "RUN", None))

    def _lstrip_textboxes(self):
        attributes = [item for item in vars(self) if not item.startswith('__')]

        for item in attributes:
            item = getattr(self, item)
            if isinstance(item, QLineEdit):
                strlength = len(item.text())
                cursorPos = item.cursorPosition()
                item.setText(item.text().lstrip())
                item.setCursorPosition(
                    cursorPos - (strlength - len(item.text())))
            elif isinstance(item, QPlainTextEdit):
                sliderPos = item.verticalScrollBar().sliderPosition()
                item.setPlainText(item.toPlainText().lstrip())
                item.verticalScrollBar().setSliderPosition(sliderPos)
