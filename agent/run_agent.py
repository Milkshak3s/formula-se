"""Launcher entry point for the packaged executable.

PyInstaller runs its target script as ``__main__``; targeting
``fse_agent/__main__.py`` directly would break its relative imports. This shim
imports the package by absolute name instead, so ``pyinstaller run_agent.py``
bundles ``fse_agent`` correctly. For normal use prefer ``python -m fse_agent``.
"""
from fse_agent.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
