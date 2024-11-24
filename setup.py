import os
import setuptools

THIS_DIR = os.path.dirname(__file__)
REQUIREMENTS_FILES = [os.path.join(THIS_DIR, 'requirements.txt')]
VERSION_FILE = os.path.join(THIS_DIR, 'VERSION')

required = []
for file_name in REQUIREMENTS_FILES:
    # Not sure why but tox seems to miss the file here
    # So add the check
    if os.path.exists(file_name):
        with open(file_name) as f:
            required += f.read().splitlines()

# Try/catch mostly here for tox.ini
try:
    with open(VERSION_FILE) as r:
        version = r.read().strip()
except FileNotFoundError:
    version = '0.0.1'

setuptools.setup(
    name='backup_tool',
    description='Backup Tool File Manager',
    author='Tyler D. North',
    author_email='me@tyler-north.com',
    install_requires=required,
    entry_points={
        'console_scripts' : [
            'backup-tool = backup_tool.cli.client:main',
        ]
    },
    packages=setuptools.find_packages(exclude=['htmlcov','tests']),
    version=version,
)
