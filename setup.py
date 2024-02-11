import os
import sys
from cx_Freeze import setup, Executable

include_files = ["bin/"]
excludes = ["tkinter"]

options = {
    "build_exe": {"optimize": 4, "excludes": excludes, "include_files": include_files}
}

executables = [
    Executable("GeckoLoader.py"),
]

setup(
    name="GeckoLoader",
    version="7.1.1",
    description="DOL Patcher for extending the codespace of Wii/GC games",
    executables=[Executable("GeckoLoader.py", icon=os.path.join("bin", "icon.ico"))],
    author="JoshuaMK",
    author_email="joshuamkw2002@gmail.com",
    options=options,
)
