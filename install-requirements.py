import platform
import subprocess

# Get the current operating system
os = platform.system().lower()

# Install the appropriate requirements file
if os == 'windows':
    subprocess.run(['pip', 'install', '-r', './requirements/requirements-windows.txt'])
elif os == 'linux':
    subprocess.run(['pip', 'install', '-r', './requirements/requirements-linux.txt'])
elif os == 'darwin':  # MacOS
    subprocess.run(['pip', 'install', '-r', './requirements/requirements-macos.txt'])
else:
    print('Unsupported operating system')
