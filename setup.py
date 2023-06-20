import setuptools

setuptools.setup(
    name='backup_tool',
    description='Backup Tool File Manager',
    author='Tyler D. North',
    author_email='ty_north@yahoo.com',
    install_requires=[
        'oci == 2.104.2',
        'pathlib == 1.0.1',
        'pycryptodome == 3.18',
        'PyYAML == 6.0',
        'SQLAlchemy == 2.0.16',
    ],
    entry_points={
        'console_scripts' : [
            'backup-tool = backup_tool.cli.client:main',
        ]
    },
    packages=setuptools.find_packages(exclude=['htmlcov','tests']),
    version='0.1.1',
)
