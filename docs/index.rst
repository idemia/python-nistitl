
NIST-ITL Parser Library
=======================

Release v\ |version|.

.. only:: html

    .. image:: https://img.shields.io/pypi/l/nistitl.svg
        :target: https://pypi.org/project/nistitl/
        :alt: CeCILL-C

    .. image:: https://img.shields.io/pypi/pyversions/nistitl.svg
        :target: https://pypi.org/project/nistitl/
        :alt: Python 3.x


Installation
------------

``nistitl`` is published on PyPI and can be installed from there::

    pip install -U nistitl

Getting Started
---------------

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

API
---

.. toctree::

    modules
