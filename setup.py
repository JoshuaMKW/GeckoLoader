import sys
from cx_Freeze import setup, Executable

options = {
    'build_exe': {
        'excludes': ['tkinter']
    }
}

executables = [
    Executable('GeckoLoader.py'),
]

setup(name='GeckoLoader',
      version='v6.0.0',
      description='DOL Patcher for extending the codespace of Wii/GC games',
      executables=executables,
      options=options
      )