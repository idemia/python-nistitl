=======
nistitl
=======

.. image:: https://readthedocs.org/projects/nistitl/badge/?version=latest
    :target: https://nistitl.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/l/nistitl.svg
    :target: https://pypi.org/project/nistitl/
    :alt: CeCILL-C

.. image:: https://img.shields.io/pypi/pyversions/nistitl.svg
    :target: https://pypi.org/project/nistitl/
    :alt: Python 3.x

.. image:: https://img.shields.io/pypi/v/nistitl.svg
    :target: https://pypi.org/project/nistitl/
    :alt: v?.?

.. image:: https://travis-ci.com/idemia/python-nistitl.svg?branch=master
    :target: https://travis-ci.com/github/idemia/python-nistitl
    :alt: Build Status (Travis CI)

.. image:: https://codecov.io/gh/idemia/python-nistitl/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/idemia/python-nistitl
    :alt: Code Coverage Status (Codecov)

A pure Python library for parsing and generating `NIST-ITL <http://dx.doi.org/10.6028/NIST.SP.500-290e3>`_
binary files.

Installation
============

``nistitl`` is published on PyPI and can be installed from there::

    pip install -U nistitl

Quick Start
===========

To generate a NIST-ITL binary message:

.. code-block:: python

    msg = nistitl.Message()
    msg.TOT = 'MY_TOT'

    r2 = nistitl.AsciiRecord(2)
    r2 += nistitl.Field(2,3,alias='TEST')
    msg += r2

    buffer = msg.NIST

To parse a NIST-ITL binary message:

.. code-block:: python

    msg = nistitl.Message()
    msg.parse(buffer)
    print("The TOT is ",msg.TOT)
    for record in msg.iter(2):
        print("Field 2.003 is ",record._3)

See `the full documentation <http://nistitl.readthedocs.io/>`_ for more details.


