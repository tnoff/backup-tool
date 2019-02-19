import setuptools

setuptools.setup(
    name='backup_tool',
    description='Backup Tool File Manager',
    author='Tyler D. North',
    author_email='ty_north@yahoo.com',
    install_requires=[
        'pyAesCrypt >= 0.4.2',
        'oci >= 2.2.0',
    ],
    entry_points={
        'console_scripts' : [
            'object-cli = backup_tool.cli.object:main',
        ]
    },
    packages=setuptools.find_packages(exclude=['tests']),
    version='0.0.1',
)
