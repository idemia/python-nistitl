
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

Full Example
------------

Build a NIST
""""""""""""

.. code-block:: python

    msg = nistitl.Message()
    msg.TOT = 'MY_TOT'
    msg[0].TCN = 'TCN'

    # --- Add a type 2 record
    r2 = nistitl.AsciiRecord(2)
    msg += r2
    r2.IDC = 1
    # Add field 2.003, long notation used to specify an alias
    r2 += nistitl.Field(2,3,alias='TEST')
    # Add field 2.004, with 2 subfields) using the short notation
    r2._4 = ('SF1', 'SF2')

    # --- Add a type 4 record
    r4 = nistitl.BinaryRecord(4)
    msg += r4
    r4.IDC = 2
    # Set all fields in one step, image and headers
    r4.pack("!BBBBBBBBHHB",             # format for ANSI/NIST-ITL 1-2011: UPDATE 2015
        1,                              # impression type (rolled contact)
        1, 255, 255, 255, 255, 255,     # finger position (right thumb)
        0,                              # image scanning resolution (500 ppi)
        500, 500,                       # width & height
        1,                              # compression algo (WSQ)
        b'image')                       # the image buffer

    # --- Add a type 10 record
    r10 = nistitl.AsciiRecord(10)
    msg += r10
    r10.IDC = 3
    # Used pre-defined alias
    r10.SRC = 'my src'
    r10.DATA = b'image'

    # Generate the NIST buffer
    buffer = msg.NIST

Parse a NIST
""""""""""""

.. code-block:: python

    msg = nistitl.Message()
    msg.parse(buffer)

    # --- Access type 2 record
    r2 = msg[(2, 1)]
    # Read field 2.003
    v = r2._3

    # --- Loop on all records of type 4
    for r4 in msg.iter(4):
        # Get all fields
        all_fields = r4.unpack("!BBBBBBBBHHB")
        imp = all_fields[0]
        fgp = list(all_fields[1:7])
        isr = all_fields[7]
        width = all_fields[8]
        height = all_fields[9]
        gca = all_fields[10]
        image = all_fields[11]

    # --- Loop on all records of type 10
    for r10 in msg.iter(10):
        # Used pre-defined alias
        src = r10.SRC
        image = r10.DATA

API
---

.. toctree::

    modules
