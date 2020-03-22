#!/usr/bin/env python

import setuptools

with open("README.rst", "r") as fh:
    long_description = fh.read()

about = {}
with open('nistitl.py', 'r') as f:
    exec(f.read(), about)

setuptools.setup(
    name = 'nistitl',
    version = about['__version__'],
    author = about['__author__'],
    author_email = "olivier.heurtier@idemia.com",
    license = about['__license__'],
    description = 'NIST-ITL Python Parsing Library',
    long_description = long_description,
    url="https://github.com/idemia/python-nistitl",
    py_modules = ['nistitl'],
    test_suite = 'tests',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: CeCILL-C Free Software License Agreement (CECILL-C)",
        "Operating System :: OS Independent",
    ],
)
