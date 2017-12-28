"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='private-postgres-rds',
    version='1.0.dev1',
    description='Private cloud / on-premises relational database service',
    long_description=long_description,
    url='http://private-postgres-rds.readthedocs.io',
    author='Vladimir Dobriakov',
    author_email='vladimir@infrastructure-as-code.de',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: System :: Systems Administration',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
    ],
    package_dir={'': 'lib'},
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=['invoke'],
    extras_require={
        'egg': ['twine','pylint','setuptools'],
        'ansible': ['ansible','yamllint'],
    },
    )
