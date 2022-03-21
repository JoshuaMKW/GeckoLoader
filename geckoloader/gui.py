
import logging
import os
import pickle as cPickle
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from enum import Enum, IntEnum
from io import StringIO
from pathlib import Path
from typing import Tuple

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QIcon, QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (QApplication, QErrorMessage, QFileDialog,
                               QMessageBox, QStyleFactory, QTextEdit)

from geckoloader import __version__
from geckoloader.children_ui import PrefWindow, SettingsWindow
from geckoloader.cli import GeckoLoaderCli
from geckoloader.fileutils import get_program_folder, resource_path
from geckoloader.gui import GeckoLoaderGUI
from geckoloader.main_ui import MainWindow


class GeckoLoaderGUI(object):

    class Dialogs(IntEnum):
        LOAD_DEST = 0
        LOAD_GCT = 1
        LOAD_FOLDER = 2
        LOAD_DOL = 3
        LOAD_SESSION = 4
        SAVE_SESSION = 5
        SAVE_SESSION_AS = 6

    def __init__(self, cli: GeckoLoaderCli):
        self.cli = cli
        self.app = None
        self.ui = None
        self.uiprefs = None
        self.uiexSettings = None
        self.dolPath = None
        self.codePath = [None, None]
        self.destPath = None
        self.sessionPath = None
        self.prefs = {"qtstyle": "Default", "darktheme": False}
        self.style_log = []
        self.compileCount = 0

        self.log = logging.getLogger(f"GeckoLoader {self.version}")

        pFolder = get_program_folder("GeckoLoader")
        if not pFolder.exists():
            pFolder.mkdir()

        hdlr = logging.FileHandler(pFolder / "error.log")
        formatter = logging.Formatter(
            "\n%(levelname)s (%(asctime)s): %(message)s")
        hdlr.setFormatter(formatter)
        self.log.addHandler(hdlr)

    def show_dialog(self, dialog_type=None):
        if dialog_type == "aboutqt":
            QMessageBox.aboutQt(self.app.activeWindow())
        elif dialog_type == "aboutGeckoLoader":
            desc = "".join(["GeckoLoader is a cross platform tool designed to give ",
                            "the user the most efficient codespace usage possible.\n\n ",
                            "This application supports various features, such as ",
                            "pre-patching codes, dynamic codehandler hooks, codespace ",
                            "extension through memory reallocation, multiple patching ",
                            "of a single DOL, and more.\n\n",
                            f"Current running version: {self.version}\n\n"
                            "Copyright (c) 2020\n\n",
                            "JoshuaMK <joshuamkw2002@gmail.com> \n\n",
                            "All rights reserved."])

            QMessageBox.about(
                self.app.activeWindow(), "About GeckoLoader", desc)
        elif dialog_type == "Preferences":
            self.uiprefs.show()
        else:
            self.uiexSettings.show()

    @property
    def version(self) -> str:
        return self.cli.__version__

    def _open_dol(self) -> Tuple[bool, str]:
        if self.dolPath is None:  # Just start in the home directory
            fname = str(QFileDialog.getOpenFileName(self.ui, "Open DOL", str(Path.home()),
                                                              "Nintendo DOL Executable (*.dol);;All files (*)")[0])
        else:  # Start in the last directory used by the user
            fname = str(QFileDialog.getOpenFileName(self.ui, "Open DOL", str(self.dolPath.parent),
                                                              "Nintendo DOL Executable (*.dol);;All files (*)")[0])

        if fname == "" or fname is None:  # Make sure we have something to open
            return False, None
        else:
            self.dolPath = Path(fname).resolve()

        if self.dolPath.is_file():
            self.ui.dolTextBox.setText(str(self.dolPath))
            return True, None
        else:
            return False, "The file does not exist!"

    def _load_codes(self, isFolder: bool = False) -> Tuple[bool, str]:
        if not isFolder:
            if self.codePath[0] is None:  # Just start in the home directory
                fname = str(QFileDialog.getOpenFileName(self.ui, "Open Codelist", str(Path.home()),
                                                                  "Gecko Code Table (*.gct);;Gecko Codelist (*.txt);;All files (*)")[0])
            else:  # Start in the last directory used by the user
                fname = str(QFileDialog.getOpenFileName(self.ui, "Open Codelist", str(self.codePath[0].parent),
                                                                  "Gecko Code Table (*.gct);;Gecko Codelist (*.txt);;All files (*)")[0])
        else:
            if self.codePath[0] is None:  # Just start in the home directory
                fname = str(QFileDialog.getExistingDirectory(self.ui, "Open Codelist", str(Path.home()),
                                                                       QFileDialog.ShowDirsOnly))
            else:  # Start in the last directory used by the user
                fname = str(QFileDialog.getExistingDirectory(self.ui, "Open Codelist", str(self.codePath[0].parent),
                                                                       QFileDialog.ShowDirsOnly))

        if fname == "" or fname is None:  # Make sure we have something to open
            return False, None
        else:
            self.codePath = [Path(fname).resolve(), isFolder]

            if not isFolder:
                self.ui.gctFileTextBox.setText(str(self.codePath[0]))
                self.ui.gctFolderTextBox.setText("")
            else:
                self.ui.gctFileTextBox.setText("")
                self.ui.gctFolderTextBox.setText(str(self.codePath[0]))

            return True, None

    def _open_dest(self) -> tuple:
        if self.dolPath is None:  # Just start in the home directory
            fname = str(QFileDialog.getOpenFileName(self.ui, "Open DOL", str(Path.home()),
                                                              "Nintendo DOL Executable (*.dol);;All files (*)")[0])
        else:  # Start in the last directory used by the user
            fname = str(QFileDialog.getOpenFileName(self.ui, "Open DOL", str(self.dolPath.parent),
                                                              "Nintendo DOL Executable (*.dol);;All files (*)")[0])

        if fname == "" or fname is None:  # Make sure we have something to open
            return False, None
        else:
            self.destPath = Path(fname).resolve()
            self.ui.destTextBox.setText(str(self.destPath))

            return True, None

    def _load_session(self) -> tuple:
        if self.sessionPath is None:
            fname = str(QFileDialog.getOpenFileName(self.ui, "Open Session", str(Path.home()),
                                                              "GeckoLoader Session (*.gprf);;All files (*)")[0])
        else:  # Start in the last directory used by the user
            fname = str(QFileDialog.getOpenFileName(self.ui, "Open Session", str(self.sessionPath.parent),
                                                              "GeckoLoader Session (*.gprf);;All files (*)")[0])

        if fname == "" or fname is None:  # Make sure we have something to open
            return False, None
        else:
            self.sessionPath = Path(fname).resolve()

            with self.sessionPath.open("rb") as session:
                p = cPickle.load(session)

                self.ui.dolTextBox.setText(p["dolPath"])

                if p["gctFilePath"] != "":
                    self.ui.gctFileTextBox.setText(p["gctFilePath"])
                    self.ui.gctFolderTextBox.setText("")
                elif p["gctFolderPath"] != "":
                    self.ui.gctFileTextBox.setText("")
                    self.ui.gctFolderTextBox.setText(p["gctFolderPath"])
                else:
                    self.ui.gctFileTextBox.setText("")
                    self.ui.gctFolderTextBox.setText("")

                self.ui.destTextBox.setText(p["destPath"])
                self.ui.allocLineEdit.setText(p["alloc"])
                self.ui.handlerTypeSelect.setCurrentIndex(p["handlerIndex"])
                self.ui.hookTypeSelect.setCurrentIndex(p["hookIndex"])
                self.ui.txtCodesIncludeSelect.setCurrentIndex(p["txtIndex"])
                self.uiexSettings.optimizeCodes.setChecked(p["optimize"])
                self.uiexSettings.protectCodes.setChecked(p["protect"])
                self.uiexSettings.encryptCodes.setChecked(p["encrypt"])
                self.uiexSettings.codehookLineEdit.setText(p["hookAddress"])
                self.uiexSettings.kernelHookLineEdit.setText(p["initAddress"])
                self.uiexSettings.verbositySelect.setCurrentIndex(
                    p["verbosity"])

            return True, None

    def _save_session(self, saveAs=False):
        if saveAs or self.sessionPath is None or self.sessionPath == "":
            if self.sessionPath is None:  # Just start in the home directory
                fname = str(QFileDialog.getSaveFileName(self.ui, "Save Session", str(Path.home()),
                                                                  "GeckoLoader Session (*.gprf);;All files (*)")[0])
            else:  # Start in the last directory used by the user
                fname = str(QFileDialog.getSaveFileName(self.ui, "Save Session", str(self.dolPath.parent),
                                                                  "GeckoLoader Session (*.gprf);;All files (*)")[0])

            if fname == "" or fname is None:  # Make sure we have something to open
                return False, None
            else:
                self.sessionPath = Path(fname).resolve()

        try:
            with self.sessionPath.open("wb") as session:
                p = {}

                p["dolPath"] = self.ui.dolTextBox.text().strip()
                p["gctFilePath"] = self.ui.gctFileTextBox.text().strip()
                p["gctFolderPath"] = self.ui.gctFolderTextBox.text().strip()
                p["destPath"] = self.ui.destTextBox.text().strip()
                p["alloc"] = self.ui.allocLineEdit.text().strip()
                p["handlerIndex"] = self.ui.handlerTypeSelect.currentIndex()
                p["hookIndex"] = self.ui.hookTypeSelect.currentIndex()
                p["txtIndex"] = self.ui.txtCodesIncludeSelect.currentIndex()
                p["optimize"] = self.uiexSettings.optimizeCodes.isChecked()
                p["protect"] = self.uiexSettings.protectCodes.isChecked()
                p["encrypt"] = self.uiexSettings.encryptCodes.isChecked()
                p["hookAddress"] = self.uiexSettings.codehookLineEdit.text().strip()
                p["initAddress"] = self.uiexSettings.kernelHookLineEdit.text().strip()
                p["verbosity"] = self.uiexSettings.verbositySelect.currentIndex()

                try:
                    cPickle.dump(p, session)
                except cPickle.PicklingError as e:
                    return False, str(e)

            return True, None
        except (IOError, PermissionError) as e:
            return False, str(e)

    def file_dialog_exec(self, event: Dialogs):
        try:
            if event == GeckoLoaderGUI.Dialogs.LOAD_DOL:
                status, msg = self._open_dol()
            elif event == GeckoLoaderGUI.Dialogs.LOAD_GCT:
                status, msg = self._load_codes(False)
            elif event == GeckoLoaderGUI.Dialogs.LOAD_FOLDER:
                status, msg = self._load_codes(True)
            elif event == GeckoLoaderGUI.Dialogs.LOAD_DEST:
                status, msg = self._open_dest()
            elif event == GeckoLoaderGUI.Dialogs.LOAD_SESSION:
                status, msg = self._load_session()
            elif event == GeckoLoaderGUI.Dialogs.SAVE_SESSION:
                status, msg = self._save_session()
            elif event == GeckoLoaderGUI.Dialogs.SAVE_SESSION_AS:
                status, msg = self._save_session(True)
            else:
                return
        except IndexError:
            self.ui.set_edit_fields()
            return

        if status is False and msg is not None:
            reply = QErrorMessage(self)
            reply.setWindowTitle("I/O Failure")
            reply.setText(msg)
            reply.setInformativeText("Please try again.")
            reply.setIcon(QMessageBox.Warning)
            reply.setStandardButtons(QMessageBox.Ok)
            reply.exec_()
        else:
            self.ui.set_edit_fields()

    def close_session(self):
        self.dolPath = None
        self.codePath = None
        self.sessionPath = None
        self.ui.dolTextBox.setText("")
        self.ui.gctFileTextBox.setText("")
        self.ui.gctFolderTextBox.setText("")
        self.ui.destTextBox.setText("")
        self.ui.allocLineEdit.setText("")
        self.ui.handlerTypeSelect.setCurrentIndex(0)
        self.ui.hookTypeSelect.setCurrentIndex(0)
        self.ui.txtCodesIncludeSelect.setCurrentIndex(0)
        self.ui.optimizeSelect.setCurrentIndex(0)
        self.ui.responses.setPlainText("")
        self.uiexSettings.protectCodes.setChecked(False)
        self.uiexSettings.encryptCodes.setChecked(False)
        self.uiexSettings.codehookLineEdit.setText("")
        self.uiexSettings.kernelHookLineEdit.setText("")
        self.uiexSettings.verbositySelect.setCurrentIndex(0)
        self.ui.set_edit_fields()

    def load_prefs(self):
        datapath = get_program_folder("GeckoLoader")

        try:
            with (datapath / ".GeckoLoader.conf").open("rb") as f:
                try:
                    p = cPickle.load(f)
                except cPickle.UnpicklingError as e:
                    self.log.exception(e)  # Use defaults for prefs
                else:
                    # Input validation
                    if (p.get("qtstyle") in list(QStyleFactory.keys()) or
                            p.get("qtstyle") == "Default"):
                        self.prefs["qtstyle"] = p.get("qtstyle")

                    if p.get("darktheme") in (True, False):
                        self.prefs["darktheme"] = p.get("darktheme")

                    setCIndex = self.uiprefs.qtstyleSelect.setCurrentIndex

                    if self.prefs.get("qtstyle") in (None, "Default"):
                        setCIndex(0)
                    else:
                        setCIndex(self.uiprefs.qtstyleSelect.findText(
                                  self.prefs.get("qtstyle"),
                                  flags=Qt.MatchFixedString))

                    self.uiprefs.qtdarkButton.setChecked(
                        self.prefs.get("darktheme"))
                    self.update_theme()

        except FileNotFoundError:
            self.log.warning("No preferences file found; using defaults.")

    def save_prefs(self):
        datapath = get_program_folder("GeckoLoader")

        self.prefs["qtstyle"] = str(self.uiprefs.qtstyleSelect.currentText())
        self.prefs["darktheme"] = self.uiprefs.qtdarkButton.isChecked()

        try:
            with (datapath / ".GeckoLoader.conf").open("wb") as f:
                cPickle.dump(self.prefs, f)
        except IOError as e:
            self.log.exception(e)

    def load_qtstyle(self, style, first_style_load=False):
        self.style_log.append(
            [self.app.style, self.uiprefs.qtstyleSelect.currentText()])

        if len(self.style_log) > 2:
            self.style_log.pop(0)

        if style != "Default":
            self.app.setStyle(style)
        else:
            self.app.setStyle(self.default_qtstyle)

        if first_style_load:
            setCIndex = self.uiprefs.qtstyleSelect.setCurrentIndex
            setCIndex(self.uiprefs.qtstyleSelect.findText(style,
                                                          flags=Qt.MatchFixedString))

    def update_theme(self):
        if self.uiprefs.qtdarkButton.isChecked():
            self.app.setPalette(self.ui.DarkTheme)
            self.load_qtstyle("Fusion", True)
            self.uiprefs.qtstyleSelect.setDisabled(True)
        else:
            self.app.setPalette(self.ui.LightTheme)
            self.load_qtstyle(self.style_log[0][1], True)
            self.uiprefs.qtstyleSelect.setEnabled(True)

    def display_update(self):
        _outpipe = StringIO()
        _errpipe = StringIO()

        with redirect_stdout(_outpipe), redirect_stderr(_errpipe):
            try:
                self.cli.check_updates()
            except SystemExit:
                _status = False
            else:
                _status = True

        icon = QIcon()
        icon.addPixmap(QPixmap(
            str(resource_path(Path("bin/icon.ico")))), QIcon.Normal, QIcon.Off)

        if _status is False:
            reply = QErrorMessage()
            reply.setWindowIcon(icon)
            reply.setWindowTitle("Response Error")
            reply.setText(self._remove_ansi(_errpipe.getvalue()))
            reply.setInformativeText(
                "Make sure you have an internet connection")
            reply.setIcon(QMessageBox.Warning)
            reply.setStandardButtons(QMessageBox.Ok)
            reply.exec_()
        else:
            reply = QMessageBox()
            reply.setWindowIcon(icon)
            reply.setWindowTitle("Update Info")
            reply.setText(self._remove_ansi(_outpipe.getvalue()).strip(
                "\n") + "\n\nYou can find all GeckoLoader releases at:\nhttps://github.com/JoshuaMKW/GeckoLoader/releases")
            reply.setIcon(QMessageBox.Information)
            reply.setStandardButtons(QMessageBox.Ok)
            reply.exec_()

    def connect_signals(self):
        self.ui.actionPreferences.triggered.connect(
            lambda: self.show_dialog("Preferences"))
        self.ui.actionAbout_Qt.triggered.connect(
            lambda: self.show_dialog("aboutqt"))
        self.ui.actionAbout_GeckoLoader.triggered.connect(
            lambda: self.show_dialog("aboutGeckoLoader"))
        self.ui.actionCheck_Update.triggered.connect(
            lambda: self.display_update())

        self.ui.actionOpen.triggered.connect(
            lambda: self.file_dialog_exec(GeckoLoaderGUI.Dialogs.LOAD_SESSION))
        self.ui.actionClose.triggered.connect(lambda: self.close_session())
        self.ui.actionSave_As.triggered.connect(
            lambda: self.file_dialog_exec(GeckoLoaderGUI.Dialogs.SAVE_SESSION_AS))
        self.ui.actionSave.triggered.connect(
            lambda: self.file_dialog_exec(GeckoLoaderGUI.Dialogs.SAVE_SESSION))

        self.ui.dolButton.clicked.connect(
            lambda: self.file_dialog_exec(GeckoLoaderGUI.Dialogs.LOAD_DOL))
        self.ui.gctFileButton.clicked.connect(
            lambda: self.file_dialog_exec(GeckoLoaderGUI.Dialogs.LOAD_GCT))
        self.ui.gctFolderButton.clicked.connect(
            lambda: self.file_dialog_exec(GeckoLoaderGUI.Dialogs.LOAD_FOLDER))
        self.ui.destButton.clicked.connect(
            lambda: self.file_dialog_exec(GeckoLoaderGUI.Dialogs.LOAD_DEST))

        self.ui.dolTextBox.textChanged.connect(
            lambda: self.ui.set_edit_fields())
        self.ui.gctFolderTextBox.textChanged.connect(
            lambda: self.ui.set_edit_fields())
        self.ui.gctFileTextBox.textChanged.connect(
            lambda: self.ui.set_edit_fields())
        self.ui.destTextBox.textChanged.connect(
            lambda: self.ui.set_edit_fields())

        self.ui.allocLineEdit.textChanged.connect(
            lambda: self._enforce_mask(self.ui.allocLineEdit, 0xFFFFFC))

        self.ui.exOptionsButton.clicked.connect(
            lambda: self.show_dialog("Advanced Settings"))
        self.ui.compileButton.clicked.connect(lambda: self._exec_api())

        self.uiprefs.buttonBox.accepted.connect(self.save_prefs)
        self.uiprefs.qtstyleSelect.currentIndexChanged.connect(
            lambda: self.load_qtstyle(self.uiprefs.qtstyleSelect.currentText()))
        self.uiprefs.qtdarkButton.clicked.connect(lambda: self.update_theme())

        self.uiexSettings.codehookLineEdit.textChanged.connect(lambda: self._enforce_mask(
            self.uiexSettings.codehookLineEdit, 0x817FFFFC, 0x80000000))
        self.uiexSettings.kernelHookLineEdit.textChanged.connect(lambda: self._enforce_mask(
            self.uiexSettings.kernelHookLineEdit, 0x817FFFFC, 0x80000000))

    def run(self):
        if sys.platform != "win32":
            datapath = Path.home() / ".GeckoLoader"
        else:
            datapath = Path(os.getenv("APPDATA")) / "GeckoLoader"

        if not datapath.is_dir():
            datapath.mkdir()

        self.app = QApplication(sys.argv)
        self.default_qtstyle = self.app.style().objectName()
        self.ui = MainWindow(self.version)
        self.uiprefs = PrefWindow()
        self.uiexSettings = SettingsWindow()

        self.uiprefs.qtstyleSelect.addItem("Default")

        styleKeys = list(QStyleFactory.keys())
        self.uiprefs.qtstyleSelect.addItems(styleKeys)

        self.load_prefs()
        self.load_qtstyle(self.prefs.get("qtstyle"), True)

        regex = QRegularExpression("[0-9A-Fa-f]*")
        validator = QRegularExpressionValidator(regex)
        self.ui.allocLineEdit.setValidator(validator)
        self.uiexSettings.codehookLineEdit.setValidator(validator)
        self.uiexSettings.kernelHookLineEdit.setValidator(validator)

        self.connect_signals()
        self.ui.show()
        sys.exit(self.app.exec_())

    def _exec_api(self):
        if sys.platform == "win32":
            self.ui.responses.appendPlainText(
                f"| Session {self.compileCount} |".center(84, "=") + "\n")
        else:
            self.ui.responses.appendPlainText(
                f"| Session {self.compileCount} |".center(76, "=") + "\n")

        self.compileCount += 1

        if self.ui.dolTextBox.isEnabled and self.ui.dolTextBox.text().strip() != "":
            dol = self.ui.dolTextBox.text().strip()
        else:
            self.ui.responses.appendPlainText(
                "DOL is missing, please add the path to your codes in the respective textbox" + "\n\n")
            return

        if self.ui.gctFileTextBox.isEnabled and self.ui.gctFileTextBox.text().strip() != "":
            gct = self.ui.gctFileTextBox.text().strip()
        elif self.ui.gctFolderTextBox.isEnabled and self.ui.gctFolderTextBox.text().strip() != "":
            gct = self.ui.gctFolderTextBox.text().strip()
        else:
            self.ui.responses.appendPlainText(
                "GCT is missing, please add the path to your codes in the respective textbox" + "\n\n")
            return

        alloc = self.ui.allocLineEdit.text().strip()
        hookType = self.ui.hookTypeSelect.currentText().strip()
        hookAddress = self.uiexSettings.codehookLineEdit.text().strip()
        initAddress = self.uiexSettings.kernelHookLineEdit.text().strip()
        txtInclude = self.ui.txtCodesIncludeSelect.currentText().strip()
        codeHandlerType = self.ui.handlerTypeSelect.currentText().strip()
        optimize = self.uiexSettings.optimizeCodes.isChecked()
        protect = self.uiexSettings.protectCodes.isChecked()
        encrypt = self.uiexSettings.encryptCodes.isChecked()
        verbosity = int(
            self.uiexSettings.verbositySelect.currentText().strip())
        dest = self.ui.destTextBox.text().strip()

        argslist = [dol, gct, "-t", txtInclude, "--handler",
                    codeHandlerType, "--hooktype", hookType]

        if alloc != "":
            argslist.append("-a")
            argslist.append(hex(int(alloc, 16) & 0xFFFFFC)[2:].upper())

        if hookAddress != "":
            if int(hookAddress, 16) < 0x80000000:
                self.ui.responses.appendPlainText(
                    "The specified code hook is invalid" + "\n")
                return

            argslist.append("--hookaddress")
            argslist.append(hookAddress)

        if initAddress != "":
            if int(initAddress, 16) < 0x80000000:
                self.ui.responses.appendPlainText(
                    "The specified initialization address is invalid" + "\n")
                return

            argslist.append("-i")
            argslist.append(initAddress)

        if dest != "":
            if dest.lower().endswith(".dol") and len(dest) > 4:
                argslist.append("--dest")
                argslist.append(dest)
            else:
                self.ui.responses.appendPlainText(
                    "The destination file path is not a valid DOL file\n")
                return

        if optimize:
            argslist.append("-o")

        if protect:
            argslist.append("-p")

        if encrypt:
            argslist.append("--encrypt")

        if verbosity > 0:
            argslist.append("-" + "v"*verbosity)
        else:
            argslist.append("-q")

        args = self.cli.parse_args(argslist)

        _outpipe = StringIO()
        _errpipe = StringIO()
        _status = False
        _msg = ""

        with redirect_stdout(_outpipe), redirect_stderr(_errpipe):
            try:
                self.cli._exec(args)
            except (SystemExit, Exception):
                _status = False
            else:
                _status = True

        if _status is False:
            _msg = f"Arguments failed! GeckoLoader couldn't execute the job\n\nArgs: {args.__repr__()}\n\nstderr: {self._remove_ansi(_errpipe.getvalue())}"
            self.ui.responses.appendPlainText(_msg.strip() + "\n")
        else:
            for line in self._remove_ansi(_outpipe.getvalue()).split("\n"):
                _msg += line.lstrip() + "\n"
            self.ui.responses.appendPlainText(_msg.strip() + "\n")

    @staticmethod
    def _enforce_mask(textbox: QTextEdit, mask: int, _or: int = 0):
        textbox.setText(textbox.text().strip())
        if len(textbox.text()) > 0:
            _depth = len(hex(mask)[2:])
            _address = int(textbox.text(), 16) << (
                (_depth - len(textbox.text())) << 2)

            aligned = hex(((_address & mask) | _or) >> (
                (_depth - len(textbox.text())) << 2))[2:].upper()
            textbox.setText(aligned)

    @staticmethod
    def _remove_ansi(msg: str) -> str:
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', msg)
