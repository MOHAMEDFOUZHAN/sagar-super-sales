import platform, sys, collections

# WMI bypass patch for Pyinstaller
if sys.platform == "win32":
    Uname = collections.namedtuple("uname_result", ["system", "node", "release", "version", "machine", "processor"])
    platform.uname = lambda: Uname("Windows", "PC", "10", "10.0.19041", "AMD64", "AMD64")
    platform.system = lambda: "Windows"
    platform.release = lambda: "10"
    platform.machine = lambda: "AMD64"
    platform.version = lambda: "10.0.19041"

import PyInstaller.__main__

PyInstaller.__main__.run([
    '--noconfirm',
    '--onefile',
    '--windowed',
    '--add-data', 'frontend;frontend',
    '--add-data', 'database;database',
    '--name', 'SagarBilling',
    '--noupx',
    'app.py'
])
