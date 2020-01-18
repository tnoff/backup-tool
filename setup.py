import setuptools

setuptools.setup(
    name='backup_tool',
    description='Backup Tool File Manager',
    author='Tyler D. North',
    author_email='ty_north@yahoo.com',
    install_requires=[
        'oci >= 2.2.0',
        'pycrypto >= 2.6.1',
        'SQLAlchemy >= 1.3.8',
    ],
    entry_points={
        'console_scripts' : [
            'object-cli = backup_tool.cli.object:main',
            'backup-tool = backup_tool.cli.client:main',
        ]
    },
    packages=setuptools.find_packages(exclude=['tests']),
    version='0.0.13',
)
