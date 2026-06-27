import platform
import sys
import collections

# WMI bypass patch for Pyinstaller
if sys.platform == "win32":
    Uname = collections.namedtuple("uname_result", ["system", "node", "release", "version", "machine", "processor"])
    platform.uname = lambda: Uname("Windows", "PC", "10", "10.0.19041", "AMD64", "AMD64")
    platform.system = lambda: "Windows"
    platform.release = lambda: "10"
    platform.machine = lambda: "AMD64"
    platform.version = lambda: "10.0.19041"

print("Starting PyInstaller build process...")
import PyInstaller.__main__
import os

# Build as a single EXE as requested, but with high-compatibility flags
PyInstaller.__main__.run([
    '--noconfirm',
    '--onefile',             
    '--windowed',            
    '--icon', 'frontend/images/app_icon.ico',
    '--add-data', 'frontend;frontend',
    '--add-data', 'database;database',
    '--add-data', '.env;.',
    '--hidden-import', 'engineio.async_drivers.threading',
    '--hidden-import', 'simple_websocket',
    '--hidden-import', 'wsproto',
    '--collect-all', 'flask',
    '--collect-all', 'flask_socketio',
    '--collect-all', 'engineio',
    '--collect-all', 'socketio',
    '--collect-all', 'charset_normalizer',
    '--collect-all', 'mysql',
    '--name', 'SSMP',
    '--clean',              
    '--noupx',              
    'app.py'
])
print("Build process finished. The single executable is in the 'dist' folder.")
