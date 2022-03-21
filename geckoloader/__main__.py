# Written by JoshuaMK 2020

from argparse import Namespace
import atexit
from enum import Enum
import logging
import os
import pickle as cPickle
import re
import shutil
import signal
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from distutils.version import LooseVersion
from io import StringIO
from pathlib import Path
from typing import Any, Dict

from PyQt5 import QtCore, QtGui, QtWidgets
from geckoloader.gui import GeckoLoaderGUI

from pyfile.children_ui import PrefWindow, SettingsWindow
from dolreader.dol import DolFile
from fileutils import get_program_folder, resource_path
from kernel import CodeHandler, KernelLoader
from main_ui import MainWindow
from tools import CommandLineParser, color_text
from versioncheck import Updater
from geckoloader import __version__
from geckoloader.cli import GeckoLoaderCli




if __name__ == "__main__":
    cli = GeckoLoaderCli('GeckoLoader', __version__,
                         description='Dol editing tool for allocating extended codespace')

    if len(sys.argv) == 1:
        cli.print_splash()
        app = GeckoLoaderGUI(cli)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        app.run()
    elif '--checkupdate' in sys.argv:
        cli.check_updates()
    elif '--splash' in sys.argv:
        cli.print_splash()
    else:
        args = cli.parse_args()
        cli._exec(args, TMPDIR)
