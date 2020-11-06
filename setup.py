import sys
from cx_Freeze import setup, Executable

options = {
    'build_exe': {
        'optimize': 4,
        'excludes': ['tkinter']
    }
}

executables = [
    Executable('GeckoLoader.py'),
]

setup(name='GeckoLoader',
      version='v7.0.0',
      description='DOL Patcher for extending the codespace of Wii/GC games',
      executables=executables,
      options=options
      )