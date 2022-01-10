
"""
nistitl
~~~~~~~

This module defines classes used to parse and generate
`NIST-ITL <http://dx.doi.org/10.6028/NIST.SP.500-290e3>`_ binary files.

The creation of a NIST file is done first with the creation of a message:

>>> msg = Message()

The message automatically contains a type 1 record. It can be accessed using
direct accessors. For instance:

>>> msg.TOT = 'TOTFORTEST'
>>> print(msg.TOT)
TOTFORTEST

Note that some fields can be accessed only in read-only mode:

>>> print(msg.CNT.NIST == b'1.003:1\\x1f0')
True
>>> msg.CNT = 12 #doctest: +IGNORE_EXCEPTION_DETAIL
Traceback (most recent call last):
    ...
AttributeError: can't set attribute

Record are created and then added to the message:

>>> r2 = AsciiRecord(2)
>>> r2.IDC = 1
>>> msg += r2

Many fields (as per the NIST-ITL specifications) are declared automatically.
Other fields are created individually by specifying the record type, the field
number, a value, a type and a format.

>>> f12 = Field(2, 12, 'TEST12', alias='f12')
>>> f12.add_subfields( SubField('TEST12-SF1') )
>>> f12.add_subfields( SubField('TEST12-SF2') )
>>> r2 = r2 + f12
>>> print(f12.NIST == b'2.012:TEST12-SF1\\x1eTEST12-SF2')
True

The alias can be used to access the field in the record. This makes the code easier to read.

>>> print(r2.f12)
['TEST12-SF1', 'TEST12-SF2']

Adding sub fields has deleted the value of the field itself:

>>> print(r2['f12']._value)
<BLANKLINE>

Or to change a value

>>> msg[0].DAT = '20090924'
>>> msg[0].TCN = '12345'

And then the full message can be generated

>>> print(msg.NIST == b'1.001:123\\x1d1.002:0400\\x1d1.003:1\\x1f1\\x1e2\\x1f1\\x1d1.004:TOTFORTEST\\x1d1.005:20090924\\x1d1.007:000\\x1d1.008:000\\x1d1.009:12345\\x1d1.011:00.00\\x1d1.012:00.00\\x1c2.001:45\\x1d2.002:1\\x1d2.012:TEST12-SF1\\x1eTEST12-SF2\\x1c')
True

Two records of the same type can be created in the message.
Record are created and then added to the message:

>>> r2 = AsciiRecord(2)
>>> r2.IDC = 2
>>> msg += r2
>>> f12 = Field(2, 12, 'TEST12', alias='f12')
>>> r2 += f12
>>> s =msg.NIST
>>> print(s == b'1.001:127\\x1d1.002:0400\\x1d1.003:1\\x1f2\\x1e2\\x1f1\\x1e2\\x1f2\\x1d1.004:TOTFORTEST\\x1d1.005:20090924\\x1d1.007:000\\x1d1.008:000\\x1d1.009:12345\\x1d1.011:00.00\\x1d1.012:00.00\\x1c2.001:45\\x1d2.002:1\\x1d2.012:TEST12-SF1\\x1eTEST12-SF2\\x1c2.001:30\\x1d2.002:2\\x1d2.012:TEST12\\x1c')
True

A NIST  buffer can be parsed easily with:

>>> msg = Message()
>>> msg.parse(s)
>>> f12 = msg[(2,'1')][12]
>>> print(f12.NIST == b'2.012:TEST12-SF1\\x1eTEST12-SF2')
True
>>> print(f12[0].value)
TEST12-SF1
>>> print(f12[1].value)
TEST12-SF2
>>> f12 = msg[(2,'2')][12]
>>> print(f12.NIST == b'2.012:TEST12')
True

Record can be directy accessed through their position (index) in the full message:

>>> print(msg[0]['CNT'][0].values == ['1', '2'])
True
>>> print(msg[0]['CNT'][1].values == ['2', '1'])
True

"""

# XXX use :class: or :method: everywhere in the docstring

import datetime
import re
import uuid
import struct
import warnings
import enum

__version__ = "0.5"
__author__ = "Olivier Heurtier"
__copyright__ = "IDEMIA"
__license__ = "CeCILL-C"

RE_TAG_LEN = re.compile(b'(?P<record>\\d+)\\.(?P<tag>\\d+)\\:(?P<value>\\d+)')
RE_TAG_BEGIN = re.compile(r'(?P<record>\d+)\.(?P<tag>\d+)\:')
RE_TAG_CONTENT = re.compile(b'(?P<tag>\\d+\\.\\d+\\:)(?P<content>.*)', re.DOTALL)

# NIST Separators
FS = b'\x1c'
GS = b'\x1d'
RS = b'\x1e'
US = b'\x1f'

#_______________________________________________________________________________
# Exception specific to this package, required not to hide the Exception that
# can result from a syntax error

@enum.unique
class NistError(enum.Enum):
    BAD_RECORD = 1
    BAD_TAG_NAME = 2
    BAD_TAG_FORMAT = 3
    BAD_RECORD_NUMBER = 4
    BAD_CONTENT = 5
    CANNOT_ADD_TYPE1 = 6
    CANNOT_DELETE_TYPE1 = 7
    RECORD_NOT_FOUND = 8
    RECORD_NOT_TERMINATED = 9
    NIST_TOO_SHORT = 10
    NIST_TOO_LONG = 11
    BAD_TAG_DUPLICATE = 12
    BAD_ALIAS_DUPLICATE = 13
    UNKNOWN_ATTRIBUTE = 14
    BAD_FIELD_VALUE = 15
    BAD_SUBFIELD_VALUE = 16

class NistException(Exception):
    """
    Exception class used to report errors generated from this module.
    """
    def __init__(self, message, error):
        super().__init__(message)
        self.error = error

    def __str__(self):
        return '{}: {}'.format(self.error.name, super().__str__())

def parse_record(buffer, push_record, push_field, push_subfield, push_value):
    """
    Parse a single "text" record
    """
    if buffer and buffer[-1] == 28:
        buffer = buffer[:-1]
    for rec in re.split(FS, buffer):
        if not rec:
            break

        for field in re.split(GS, rec):
            mo = RE_TAG_CONTENT.match(field)
            if not mo:
                # this is due to invalid len in current record but don't know if too short or too long
                # return Invalid record data
                raise NistException("Invalid record data", NistError.BAD_RECORD)
            sfs = mo.group('content').split(RS)
            for sf in sfs:
                items = sf.split(US)
                if len(items) == 1 and len(sfs) == 1:
                    push_field(mo.group('tag').decode('latin-1'), items[0])
                    break
                if len(items) != 1:
                    for i in items:
                        push_value(i)
                    push_subfield(None)
                else:
                    push_subfield(items[0])
            if len(sfs) != 1 or len(items) != 1:
                push_field(mo.group('tag').decode('latin-1'), None)
        push_record()

#_______________________________________________________________________________
class _Parser(object):
    def __init__(self, record):
        self._record = record
        self._subfields = []
        self._values = []
        self.closed = False
        self.encoding = 'latin-1'
    def push_record(self):
        # we parse a single record, no action here
        # (flag the event and use it to detect syntax error)
        self.closed = True
    def push_field(self, tag, value):
        mo = RE_TAG_BEGIN.match(tag)
        if not mo:
            raise NistException("Illegal tag name %s" % tag, NistError.BAD_TAG_NAME)
        record = int(mo.group('record'))
        if record != self._record.type:
            raise NistException("Illegal record number in tag name %s" % tag, NistError.BAD_RECORD_NUMBER)
        tag = int(mo.group('tag'))
        f = self._record[tag]
        if not f:
            f = Field(self._record.type, tag)
            self._record += f
        f.reset()
        if value:
            # IDC are numeric by the specs
            if (record != 1 and tag == 2) or (tag == 1):
                f.value = int(value.decode(self.encoding))
            else:
                f.value = value.decode(self.encoding)
        else:
            f.add_subfields(*self._subfields)
        self._subfields = []
        self._values = []
    def push_subfield(self, value):
        if value:
            sf = SubField(value.decode(self.encoding))
        else:
            sf = SubField()
            sf.add_values(*self._values)
        self._subfields.append(sf)
        self._values = []
    def push_value(self, value):
        self._values.append(value.decode(self.encoding))


#_______________________________________________________________________________
class Message(object):
    """
    The Message class is the main entry point. It is used to parse an existing
    NIST file as well as for building a new one.
    """
    __slots__ = ['_records']

    def __init__(self):
        self.reset()

    def reset(self, autocreate=True, autosort=True):
        """
        Reset the record list, leaving only a blank new type-1 record.
        if *autocreate* is True, the type-1 record is initialized.
        If *autosort* is True, the tags are sorted by numeric order.
        """
        # Create type-1 record
        r1 = AsciiRecord(1, autocreate, autosort)
        self._records = [r1]

    #
    # Add records to the message
    #

    def __add__(self, record):
        """
        Add a *record* to the list of records of the message.
        Example:

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> msg = msg + r
        >>> len(msg._records)
        2
        """
        # check the record
        if record.type == 1 and self._records:
            raise NistException("Cannot add a type 1 record: it must be the first record", NistError.CANNOT_ADD_TYPE1)
        self._records.append(record)
        return self

    def __iadd__(self, record):
        """
        Add a *record* to the list of records of the message.
        Example:

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> msg += r
        >>> len(msg._records)
        2
        """
        return self.__add__(record)

    #
    # Access the records in the message
    #

    def __iter__(self):
        """
        Iterate over all the records.

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> msg = msg + r
        >>> for record in msg:
        ...     print(record.type)
        1
        2
        """
        return self._records.__iter__()

    def iter(self, type):
        """
        Return an iterator on all the records of type *type*.

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> msg = msg + r
        >>> for record in msg.iter(2):
        ...     print(record.type)
        2
        """
        ret = []
        for r in self._records:
            if r.type == type:
                ret.append(r)
        return ret.__iter__()

    def __getitem__(self, key):
        """
        Return the record identified by *key*. *key* can be:

        - a tuple or list with two integers: the record type and the record IDC
        - a single numeric value: the index in the list of records.

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> msg = msg + r

        Access the second record, whatever its type:

        >>> print(msg[1].type)
        2

        Access the first type 2 record with IDC = 0:

        >>> print(msg[(2, 0)].type)
        2

        Since type 1 has no IDC, it can only be accessed with an index of 0

        >>> print(msg[0].type)
        1

        If there is no record for the key, an exception is raised:

        >>> msg[100]
        Traceback (most recent call last):
        ...
        IndexError: list index out of range

        >>> msg[(2, 100)]
        Traceback (most recent call last):
        ...
        IndexError: list index out of range

        """
        if isinstance(key, (list, tuple)) and len(key) == 2:
            # Find the record for the type and IDC
            for r in self._records:
                if r.type == key[0] and int(r.IDC) == int(key[1]):
                    return r
            raise IndexError('list index out of range')
        return self._records[key]

    def __len__(self):
        """
        Return the number of records in the message.

        >>> msg = Message()
        >>> print(len(msg))
        1
        """
        return len(self._records)

    #
    # Remove records from the message
    #

    def __delitem__(self, key):
        """
        Delete a record. *key* can be:

        - a tuple or list containing type record type (a numeric) and the record
          IDC (a numeric)
        - a single numeric value: the index in the list of records.

        >>> msg = Message()
        >>> r = AsciiRecord(2)

        Delete the second record, whatever its type:

        >>> msg = msg + r
        >>> del msg[1]
        >>> len(msg)
        1

        Access the first type 2 record with IDC = 0:

        >>> msg = msg + r
        >>> del msg[(2, 0)]
        >>> len(msg)
        1

        Type 1 record cannot be deleted (create a new message and move or copy the records
        if you have a need for this):

        >>> msg = msg + r
        >>> del msg[(1, 0)]
        Traceback (most recent call last):
        ...
        nistitl.NistException: CANNOT_DELETE_TYPE1: Cannot delete the type 1 record

        >>> del msg[0]
        Traceback (most recent call last):
        ...
        nistitl.NistException: CANNOT_DELETE_TYPE1: Cannot delete the type 1 record

        """
        if isinstance(key, (list, tuple)) and len(key) == 2:
            if key[0] == 1:
                raise NistException("Cannot delete the type 1 record", NistError.CANNOT_DELETE_TYPE1)
            # Find the record for the type and IDC
            for r in self._records:
                if r.type == key[0] and int(r.IDC) == int(key[1]):
                    self._records.remove(r)
                    return
        if key == 0:
            raise NistException("Cannot delete the type 1 record", NistError.CANNOT_DELETE_TYPE1)
        del self._records[key]

    def __sub__(self, record):
        """
        Remove one specific record from the message.

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> msg = msg + r
        >>> len(msg)
        2
        >>> msg = msg - r
        >>> len(msg)
        1

        >>> msg = msg - r
        Traceback (most recent call last):
        ...
        nistitl.NistException: RECORD_NOT_FOUND: Cannot remove a record: record not found
        """
        for r in self._records:
            if r is record:
                self._records.remove(r)
                return self
        raise NistException("Cannot remove a record: record not found", NistError.RECORD_NOT_FOUND)

    def __isub__(self, record):
        """
        Remove one specific record from the message.

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> msg = msg + r
        >>> len(msg)
        2
        >>> msg -= r
        >>> len(msg)
        1

        >>> msg -= r
        Traceback (most recent call last):
        ...
        nistitl.NistException: RECORD_NOT_FOUND: Cannot remove a record: record not found
        """
        self.__sub__(record)
        return self

    #
    # Shortcuts
    #

    # Direct access to the TOT of the NIST (shortcut).
    def get_TOT(self):
        return self._records[0].TOT
    def set_TOT(self, v):
        self._records[0].TOT = v
    TOT = property(get_TOT, set_TOT)
    """
    Shortcut to the TOT of the message (stored in the type 1 record)
    """

    # Access to the (calculated) CNT
    @property
    def CNT(self):
        """
        Calculation of the ``CNT`` field of the type-1 record.
        Returns the :class:`Field` for the ``CNT``.

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> r.IDC = 3
        >>> msg = msg + r
        >>> msg.TOT = 'TEST'
        >>> len(msg)
        2
        >>> msg.CNT.NIST
        b'1.003:1\\x1f1\\x1e2\\x1f3'

        """
        # update CNT in type 1
        f = self._records[0]['CNT']
        f.reset()
        sf = SubField()
        f.add_subfields(sf)
        sf.add_values(1, len(self._records)-1)
        for r in self._records[1:]:
            sf = SubField()
            f.add_subfields(sf)
            sf.add_values(r.type, r.IDC)
        return f

    def __str__(self):
        """
        Build and return a summary of the NIST content. It can be useful
        to document the content of a NIST.

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> r.IDC = 3
        >>> msg = msg + r
        >>> msg.TOT = 'TEST'
        >>> msg[0].DAT = '20190517'
        >>> msg[0].TCN = 'doctest'
        >>> msg[0].TCR = 'TCR'
        >>> print(str(msg))
         1.001: LEN                           : 0
         1.002: VER                           : 0400
         1.003: CNT                           : [[1, 1], [2, 3]]
         1.004: TOT                           : TEST
         1.005: DAT                           : 20190517
         1.007: DAI                           : 000
         1.008: ORI                           : 000
         1.009: TCN                           : doctest
         1.010: TCR                           : TCR
         1.011: NSR                           : 00.00
         1.012: NTR                           : 00.00
         2.001: LEN                           : 0
         2.002: IDC                           : 3

        """
        self.CNT    # pylint: disable=pointless-statement
        return '\n'.join([str(r) for r in self._records])

    #
    # Conversion and parsing
    #

    @property
    def NIST(self):
        """
        Calculation of NIST binary content. A bytes is returned containing
        all the records previously added.

        >>> msg = Message()
        >>> msg.TOT = 'TEST'
        >>> msg[0].DAT = '20190517'
        >>> msg[0].TCN = 'doctest'
        >>> msg.NIST
        b'1.001:115\\x1d1.002:0400\\x1d1.003:1\\x1f0\\x1d1.004:TEST\\x1d1.005:20190517\\x1d1.007:000\\x1d1.008:000\\x1d1.009:doctest\\x1d1.011:00.00\\x1d1.012:00.00\\x1c'
        """
        # separator is added in the record classes
        # because binary records do not include it
        self.CNT    # pylint: disable=pointless-statement
        return b''.join([r.NIST for r in self._records]+[b''])

    def _factory(self, record, autocreate, autosort):
        if record in [3, 5, 6]:
            warnings.warn("Record of type %s" % record, DeprecationWarning, 2)
        if record in [3, 4, 5, 6, 7, 8]:
            return BinaryRecord(record)
        return AsciiRecord(record, autocreate=autocreate, autosort=autosort)

    def parse(self, buffer):
        """
        Parse a NIST buffer and initialize the list of records corresponding to
        the content.
        *buffer* must be a bytes object, not a string.

        >>> msg = Message()
        >>> r = AsciiRecord(2)
        >>> r.IDC = 3
        >>> msg = msg + r
        >>> msg.TOT = 'TEST'
        >>> msg[0].DAT = '20190517'
        >>> msg[0].TCN = 'doctest'

        >>> new_msg = Message()
        >>> new_msg.parse( msg.NIST )
        >>> len(new_msg)
        2

        If the buffer is truncated, an exception is raised:

        >>> new_msg = Message()
        >>> new_msg.parse( msg.NIST[:-1] )
        Traceback (most recent call last):
        ...
        nistitl.NistException: NIST_TOO_SHORT: NIST buffer too short (missing bytes) when parsing record 2

        If there are extra bytes to the buffer, this may indicate a binary record is truncated:

        >>> new_msg = Message()
        >>> new_msg.parse( msg.NIST + b'x12345' )
        Traceback (most recent call last):
        ...
        nistitl.NistException: BAD_CONTENT: Could not recognize binary record, bad content or bad record

        This works also with type 14 records that end with a binary buffer:

        >>> msg = Message()
        >>> msg.TOT = 'TEST'
        >>> msg[0].DAT = '20190517'
        >>> msg[0].TCN = 'doctest'
        >>> r = AsciiRecord(14)
        >>> r += Field(14, 3, 'OK')
        >>> r += BinaryField(14, 999, b'data')
        >>> msg = msg + r

        >>> new_msg = Message()
        >>> new_msg.parse( msg.NIST[:-1])
        Traceback (most recent call last):
        ...
        nistitl.NistException: NIST_TOO_SHORT: NIST buffer too short (missing bytes) when parsing record 14

        >>> new_msg = Message()
        >>> new_msg.parse( msg.NIST + b'x')
        Traceback (most recent call last):
        ...
        nistitl.NistException: NIST_TOO_LONG: NIST buffer too long (extra bytes)

        """
        self.reset(autocreate=False, autosort=True)
        offset = 0
        while offset+4 < len(buffer):
            mo = RE_TAG_LEN.match(buffer[offset:])
            if mo:
                record = int(mo.group('record'))
                length = int(mo.group('value'))

                future_exc = None

                # Get tag for DATA field
                tag_for_data = None
                for K, V in ALIASES[record].items():
                    if V == 'DATA':
                        tag_for_data = K
                        break

                # Check we have enough space left to fetch length bytes
                if not offset+length<=len(buffer):
                    # Try to parse what we have
                    length = len(buffer)-offset
                    future_exc = NistException("NIST buffer too short (missing bytes) when parsing record %s" % record, NistError.NIST_TOO_SHORT)
                else:
                    # Check we have everything we can have, i.e. either a FS or the data tag
                    if tag_for_data:
                        pos_data = buffer.find(str(tag_for_data).encode('latin-1')+b':', offset)
                    else:
                        pos_data = -1
                    pos_fs = buffer.find(FS, offset)
                    new_length = min([x for x in [pos_fs, pos_data] if x >=0]) - offset
                    if new_length>length:
                        future_exc = NistException("NIST buffer too long (extra bytes)", NistError.NIST_TOO_LONG)
                        length = new_length

                # We can now extract the buffer for this record
                record_buffer = buffer[offset:offset+length]

                if tag_for_data:
                    pos = record_buffer.find(str(tag_for_data).encode('latin-1')+b':')
                else:
                    pos = -1
                pos_end = 0
                if pos > 0:
                    pos_end = record_buffer.rfind(GS, 0, pos)

                if pos > 0 and pos_end != pos:
                    # ascii record with binary data (type 10 for instance)
                    # parse only the beginning of the record

                    # check we still are pointing to a valid tag name
                    if not RE_TAG_BEGIN.match(record_buffer[pos_end+1:pos+4].decode('latin-1')):
                        raise NistException("Illegal format for tag %s (%s)" % (tag_for_data, record_buffer[pos_end+1:pos+4].decode('latin-1')), NistError.BAD_TAG_FORMAT)

                    # parse the first part of the buffer (replace GS with FS)
                    text_buffer = record_buffer[:pos_end]+FS
                    nr = self._factory(record, False, True)
                    self += nr
                    p = _Parser(nr)
                    try:
                        parse_record(text_buffer, p.push_record, p.push_field, p.push_subfield, p.push_value)
                    except NistException as exc:
                        if future_exc:
                            raise future_exc from exc
                        raise
                    if not p.closed:
                        if future_exc:
                            raise future_exc
                        raise NistException("Record type %d not terminated"%record, NistError.RECORD_NOT_TERMINATED)

                    # Add the binary part (might be incomplete if length was wrong)
                    f = BinaryField(record, tag_for_data)
                    f.value = record_buffer[pos+4:-1]
                    nr += f
                else:
                    # pure ascii record, no binary tag
                    # parse the record
                    if record == 1:
                        p = _Parser(self._records[0])
                        try:
                            parse_record(record_buffer, p.push_record, p.push_field, p.push_subfield, p.push_value)
                        except NistException as exc:
                            if future_exc:
                                raise future_exc from exc
                            raise
                        if not p.closed:
                            if future_exc:
                                raise future_exc
                            raise NistException("Record type %d not terminated"%record, NistError.RECORD_NOT_TERMINATED)
                    else:
                        nr = self._factory(record, False, True)
                        self += nr
                        p = _Parser(nr)
                        try:
                            parse_record(record_buffer, p.push_record, p.push_field, p.push_subfield, p.push_value)
                        except NistException as exc:
                            if future_exc:
                                raise future_exc from exc
                            raise
                        if not p.closed:
                            if future_exc:
                                raise future_exc
                            raise NistException("Record type %d not terminated"%record, NistError.RECORD_NOT_TERMINATED)
                if future_exc:
                    raise future_exc
            else:
                # Extract length from the four first bytes
                length, idc = struct.unpack("!LB", buffer[offset:offset+5])
                # analyze CNT from type 1 to deduce the type of this binary record
                pos = len(self._records)+1
                CNT = self._records[0].CNT
                try:
                    record_type = int(CNT[pos-1][0])
                except IndexError as exc:
                    # Invalid record
                    raise NistException("Could not recognize binary record, bad content or bad record", NistError.BAD_CONTENT) from exc

                # Check we have enough space left to fetch length bytes
                if not offset+length<=len(buffer):
                    raise NistException("NIST buffer too short (missing bytes) when parsing record %s" % record, NistError.NIST_TOO_SHORT)

                nr = self._factory(record_type, True, True)
                nr.IDC = idc
                nr.value = buffer[offset+5:offset+length]
                self += nr

            offset += length

        # Check if there are remaining bytes not parsed
        if offset < len(buffer):
            raise NistException("NIST buffer too long (extra bytes)", NistError.NIST_TOO_LONG)

        # Check CNT fields (does it match content found during parsing ?)
        i = 0
        CNT = self._records[0]['CNT']
        if len(CNT) != len(self._records):
            raise NistException("Bad CNT tag in record 1 (different number of records)", NistError.BAD_CONTENT)
        for i in range(len(CNT)):
            if len(CNT.value[i]) != 2:
                raise NistException("Bad CNT tag in record 1 (bad number of values for subfield #%d)" % i, NistError.BAD_CONTENT)
            if i == 0:
                if int(CNT.value[i][0]) != self._records[i].type:
                    raise NistException("Bad CNT tag in record 1 (bad record type for subfield #%d)" % i, NistError.BAD_CONTENT)
            elif int(CNT.value[i][0]) != self._records[i].type and int(CNT.value[i][1]) != int(self._records[i].IDC):
                raise NistException("Bad CNT tag in record 1 (bad record type or bad IDC for subfield #%d)" % i, NistError.BAD_CONTENT)


#_______________________________________________________________________________
class AsciiRecord(object):
    """
    An ASCII record. ASCII records, or text record, contain text data encoded
    in latin-1 organized in fields, subfields and items. They can also contain
    a final field with binary data.

    When creating an AsciiRecord you can specify the option ``autosort`` to ``True``
    (the default) or to ``False``. When true, the fields will be sorted by numeric
    order, except for ``BinaryField`` that will remain at the end.
    """
    SEPARATOR = GS
    __slots__ = ['type', '_fields', '_value', '_autosort']

    def __init__(self, type, autocreate=True, autosort=True):
        self.type = type
        self._fields = []
        self._value = ''  # value for binary record
        self._autosort = autosort
        if autocreate:
            self += Field(self.type, 1, 0)
            if self.type == 1:
                # Create the mandatory fields of type 1
                self += Field(self.type, 2, '0400')
                self += Field(self.type, 3, '')
                self += Field(self.type, 4, '')
                today = datetime.datetime.today()
                v = '%04d%02d%02d' % (today.year, today.month, today.day)
                self += Field(self.type, 5, v)
                self += Field(self.type, 7, '000')
                self += Field(self.type, 8, '000')
                # generate somekind of transaction number
                self += Field(self.type, 9, uuid.uuid1().hex)
                self += Field(self.type, 11, '00.00')
                self += Field(self.type, 12, '00.00')
            else:
                self += Field(self.type, 2, 0)

    #
    # Add fields
    #
    def __add__(self, f):
        """
        Add the field *f* to the record after some consistency checks.

        >>> r = AsciiRecord(2)
        >>> r = r + Field(2, 3, 'OK')
        >>> print(str(r))
         2.001: LEN                           : 0
         2.002: IDC                           : 0
         2.003:                               : OK

        """
        # init alias based on record number
        if not f.alias:
            # force exception if type is unknown
            a = ALIASES[self.type]
            try:
                f.alias = a[f.tag]
            except KeyError:
                pass
        # Add some check (unicity of number, unicity of alias, type of record)
        if f.record != self.type:
            raise NistException("Bad record number %s for tag %d in record %s" % (f.record, f.tag, self.type), NistError.BAD_RECORD_NUMBER)
        for ff in self._fields:
            if ff.tag == f.tag:
                raise NistException("Tag %d already defined in record %s" % (f.tag, self.type), NistError.BAD_TAG_DUPLICATE)
            if f.alias and ff.alias == f.alias:
                raise NistException("Alias %s already defined in record %s" % (repr(f.alias), self.type), NistError.BAD_ALIAS_DUPLICATE)
        self._fields.append(f)
        return self

    def __iadd__(self, f):
        """
        Add the field *f* to the record after some consistency checks.

        >>> r = AsciiRecord(2)
        >>> r += Field(2, 3, 'OK')
        >>> print(str(r))
         2.001: LEN                           : 0
         2.002: IDC                           : 0
         2.003:                               : OK

        """
        self.__add__(f)
        return self

    #
    # Access fields
    #
    def __getitem__(self, tag):
        """
        Get a field from this record. The field is identified by *tag*, a number or an alias.
        If there is no such field, ``None`` is returned.

        >>> r = AsciiRecord(2)
        >>> r += Field(2, 3, 'OK', alias='test')
        >>> r[3].value
        'OK'
        >>> r['test'].value
        'OK'
        >>> print(r[4])
        None

        """
        for f in self._fields:
            if f.tag == tag or (f.alias and f.alias == tag):
                return f
        return None

    #
    # Remove fields
    #
    def __delitem__(self, tag):
        """
        Remove the field identified by *tag* from the record.
        If there is not field for this tag, no exception is raised.

        >>> r = AsciiRecord(2)
        >>> r += Field(2, 3, 'OK')
        >>> print(str(r))
         2.001: LEN                           : 0
         2.002: IDC                           : 0
         2.003:                               : OK

        >>> del r[3]
        >>> print(str(r))
         2.001: LEN                           : 0
         2.002: IDC                           : 0

        >>> del r[4]
        """
        for f in self._fields:
            if f.tag == tag:
                self._fields.remove(f)
                return

    def __str__(self):
        """
        Build and return a summary of the record. It can be useful
        to document the content of a NIST.

        >>> r = AsciiRecord(14)
        >>> r += Field(14, 3, 'OK')
        >>> r += BinaryField(14, 999, b'data')
        >>> print(str(r))
        14.001: LEN                           : 0
        14.002: IDC                           : 0
        14.003: IMP                           : OK
        14.999: DATA                          : <buffer, size=4>
        """
        ret = []
        for f in self._sorted_fields(0):
            if not isinstance(f, BinaryField):
                ret.append("{0.record:2}.{0.tag:03}: {0.alias:30}: {0.value}".format(f))
            else:
                ret.append("{0.record:2}.{0.tag:03}: {0.alias:30}: <buffer, size={1:,}>".format(f, len(f.value)))
        return '\n'.join(ret)

    #
    # Shortcuts on field values
    #
    def __setattr__(self, tag, v):
        """
        Fields can be set directly using one the following syntax:

        - *record._number*: set the value for one tag using the number of the tag
        - *record.alias* set the value for one alias. The field must already exist or the
          alias must be a standard pre-defined alias (not all of them are defined in this library).

        >>> r = AsciiRecord(10)
        >>> r.IDC = 4           # known
        >>> r._2 = 5           # known, by the tag number
        >>> r.SRC = 'my src'    # new one, predeclared
        >>> r._7 = 'my vll'     # by the tag number
        >>> r._345 = 'no alias'
        >>> print(str(r))
        10.001: LEN                           : 0
        10.002: IDC                           : 5
        10.004: SRC                           : my src
        10.007: VLL                           : my vll
        10.345:                               : no alias

        Other usage will generate exceptions

        >>> r.UUU = 'unknown alias'
        Traceback (most recent call last):
        ...
        nistitl.NistException: UNKNOWN_ATTRIBUTE: Bad attribute name <UUU> while trying to define a field in record of type 10

        >>> r._76a = 'not an integer'
        Traceback (most recent call last):
        ...
        nistitl.NistException: UNKNOWN_ATTRIBUTE: Bad attribute name <_76a> while trying to define a field in record of type 10

        It is possible to set the 999 tag with a bytes object:

        >>> r.DATA = b'data'
        >>> print(str(r))
        10.001: LEN                           : 0
        10.002: IDC                           : 5
        10.004: SRC                           : my src
        10.007: VLL                           : my vll
        10.345:                               : no alias
        10.999: DATA                          : <buffer, size=4>

        """

        if tag in ['type', '_fields', '_value', '_autosort']:
            return object.__setattr__(self, tag, v)
        # look in existing fields
        for f in self._fields:
            if f.alias == tag:
                f.value = v
                return None
        # not found, check the standard pre-defined list of alias
        A = ALIASES[self.type]
        num_tag = None
        for K, V in A.items():
            if V == tag:
                num_tag = K
                break
        if tag == 'DATA':
            self += BinaryField(self.type, num_tag, v, alias=tag)
            return None
        if num_tag:
            self += Field(self.type, num_tag, v, alias=tag)
            return None
        # Check for the syntax '_integer'
        if tag and tag[0] == '_':
            try:
                num_tag = int(tag[1:])
                # look in existing fields
                for f in self._fields:
                    if f.tag == num_tag:
                        f.value = v
                        return None
                # add a new field
                if A.get(num_tag, '') == 'DATA':
                    self += BinaryField(self.type, num_tag, v)
                else:
                    self += Field(self.type, num_tag, v)
                return None
            except ValueError:
                pass
        raise NistException("Bad attribute name <%s> while trying to define a field in record of type %s" % (tag, self.type), NistError.UNKNOWN_ATTRIBUTE)

    def __getattr__(self, tag):
        """
        Fields value can be accessed directly using one the following syntax:

        - *record._number*: get the value for one tag using the number of the tag
        - *record.alias* get the value for one alias. The field must already exist

        Build a record with some fields:

        >>> r = AsciiRecord(10)
        >>> r.IDC = 4           # known
        >>> r.SRC = 'my src'    # new one, predeclared
        >>> r._7 = 'my vll'     # by the tag number

        Access the values

        >>> r.IDC
        4
        >>> r._4
        'my src'

        >>> r.UUU       # unknown alias
        Traceback (most recent call last):
        ...
        nistitl.NistException: UNKNOWN_ATTRIBUTE: Unkown or bad attribute <UUU> while trying to retrieve a field in record of type 10

        >>> r._76a      # not an integer
        Traceback (most recent call last):
        ...
        nistitl.NistException: UNKNOWN_ATTRIBUTE: Unkown or bad attribute <_76a> while trying to retrieve a field in record of type 10

        """
        for f in self._fields:
            if f.alias == tag:
                return f.value
        if tag and tag[0] == '_':
            try:
                num_tag = int(tag[1:])
                for f in self._fields:
                    if f.tag == num_tag:
                        return f.value
            except ValueError:
                pass
        raise NistException("Unkown or bad attribute <%s> while trying to retrieve a field in record of type %s" % (tag, self.type), NistError.UNKNOWN_ATTRIBUTE)

    #
    # Conversion and parsing
    #

    def _sorted_fields(self, start):
        a = []
        b = []
        for f in self._fields[start:]:
            if not isinstance(f, BinaryField):
                a.append(f)
            else:
                b.append(f)
        if self._autosort:
            for x in sorted(a, key=lambda x: x.tag):
                yield x
        else:
            for x in a:
                yield x
        for x in b:
            yield x

    @property
    def NIST(self):
        """
        Calculation of the NIST binary representation of this record.
        A bytes object is returned.

        >>> r = AsciiRecord(10)
        >>> r.IDC = 2
        >>> r._999 = b'my image data'
        >>> print(r.NIST)
        b'10.001:40\\x1d10.002:2\\x1d10.999:my image data\\x1c'

        >>> r = AsciiRecord(1, autosort=True)
        >>> r.TCN = 'TCN'
        >>> r.TCR = 'TCR'
        >>> r.DAT = '20200904'
        >>> print(r.NIST)
        b'1.001:114\\x1d1.002:0400\\x1d1.003:\\x1d1.004:\\x1d1.005:20200904\\x1d1.007:000\\x1d1.008:000\\x1d1.009:TCN\\x1d1.010:TCR\\x1d1.011:00.00\\x1d1.012:00.00\\x1c'

        >>> r = AsciiRecord(1, autosort=False)
        >>> r.TCN = 'TCN'
        >>> r.TCR = 'TCR'
        >>> r.DAT = '20200904'
        >>> print(r.NIST)
        b'1.001:114\\x1d1.002:0400\\x1d1.003:\\x1d1.004:\\x1d1.005:20200904\\x1d1.007:000\\x1d1.008:000\\x1d1.009:TCN\\x1d1.011:00.00\\x1d1.012:00.00\\x1d1.010:TCR\\x1c'
        """
        # update the record length to match the full record side, including the LEN tag
        # make sure the binary field is at the end
        s = self.SEPARATOR.join([f.NIST for f in self._sorted_fields(1)])
        f1 = self._fields[0]
        f1.value = 0
        l = -1
        ret = ' '
        while 1:
            ret = self.SEPARATOR.join([f1.NIST, s])
            f1.value = len(ret)+1
            if l == len(ret):
                break
            l = len(ret)
        return ret+FS

#_______________________________________________________________________________
class BinaryRecord(object):
    """
    A binary record. Binary records are fully binary and are not parsed at all.
    Only the ``IDC`` is extracted.

    >>> r = BinaryRecord(4)
    >>> r.IDC = 1
    >>> r.value = b'data'
    >>> print(r.NIST)
    b'\\x00\\x00\\x00\\t\\x01data'

    >>> print(str(r))
     4.001: LEN                           : 9
     4.002: IDC                           : 1
     4.---:                               : <buffer, size=4>

    """
    __slots__ = ['type', '_IDC', 'value', 'format']
    def __init__(self, type):
        # fields: length (4 bytes), IDC (1 byte). Remaining bytes are not interpreted
        self.type = type
        self._IDC = Field(self.type, 2, 1)
        self.value = b''
        self.format = ''

    # Access to the IDC (same API as for AsciiRecord)
    def get_IDC(self):
        return self._IDC.value
    def set_IDC(self, value):
        self._IDC.value = value
    IDC = property(get_IDC, set_IDC)
    """
    Shortcut to access the IDC of the record.
    """

    # Total length of the record (calculated)
    @property
    def length(self):
        """
        Access to the record length (in bytes)
        """
        return 5+len(self.value)

    # The NIST representation of this record
    @property
    def NIST(self):
        """
        Calculation of the NIST binary representation of this record.
        A bytes object is returned.
        """
        buf = struct.pack("!LB", self.length, self.IDC)+self.value
        return buf

    # helper to parse the binary value
    def pack(self, format, *args):
        """
        A direct wrapper on struct.pack.
        If successful, the format is kept in the object and used in __str__ to improve
        the output.

        There is always an additional argument corresponding to additional data
        added to the value (usually an image data).

        >>> r = BinaryRecord(4)
        >>> r.IDC = 1
        >>> r.pack("!LHB", 3, 2, 1, b'my image data')
        >>> print(r.NIST)
        b'\\x00\\x00\\x00\\x19\\x01\\x00\\x00\\x00\\x03\\x00\\x02\\x01my image data'

        >>> print(str(r))
         4.001: LEN                           : 25
         4.002: IDC                           : 1
         4.---:                               : <buffer, size=20>
                                              -> 3
                                              -> 2
                                              -> 1
        """
        self.value = struct.pack(format, *args[:-1]) + args[-1]
        self.format = format

    def unpack(self, format):
        """
        Unpack the value of the record (without the length and the IDC) and return
        the value described in the format and the remaining buffer (usually an image data)

        If successful, the format is kept in the object and used in __str__ to improve
        the output.

        >>> r = BinaryRecord(4)
        >>> r.IDC = 1
        >>> r.pack("!LHB", 3, 2, 1, b'my image data')
        >>> r.unpack("!BHL")    # format changed for the test!
        (0, 0, 50332161, b'my image data')

        >>> print(str(r))
         4.001: LEN                           : 25
         4.002: IDC                           : 1
         4.---:                               : <buffer, size=20>
                                              -> 0
                                              -> 0
                                              -> 50332161
        """
        size = struct.calcsize(format)
        result = struct.unpack(format, self.value[:size])
        self.format = format
        return result+(self.value[size:],)

    # Nice display
    def __str__(self):
        ret = []
        ret.append("{0:2}.{1:03}: {2:30}: {3}".format(self.type, 1, 'LEN', self.length))
        ret.append("{0:2}.{1:03}: {2:30}: {3}".format(self.type, 2, 'IDC', self.IDC))
        ret.append("{0:2}.---: {1:30}: <buffer, size={2:,}>".format(self.type, '', len(self.value)))
        if self.format:
            size = struct.calcsize(self.format)
            args = struct.unpack(self.format, self.value[:size])
            for arg in args:
                ret.append("        {0:30}-> {1}".format('', arg))

        return '\n'.join(ret)

#_______________________________________________________________________________
class Field(object):
    """
    A class representing a field added to an :class:`AsciiRecord`.

    A field can be configured to accept only a single value (no subfields, no items)

    >>> f = Field(2, 3, type="F")
    >>> f.value = 'ok'
    >>> f.value = [1, 2]
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_FIELD_VALUE: Field 2.003: cannot have subfields
    >>> f.value = [[1, 2]]
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_FIELD_VALUE: Field 2.003: cannot have subfields

    Or only a subfield:

    >>> f = Field(2, 3, type="S")
    >>> f.value = [1, 2]
    >>> f.value = 'ok'
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_FIELD_VALUE: Field 2.003: cannot have a value (only subfields and/or items)
    >>> f.value = [[1, 2]]
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_SUBFIELD_VALUE: Subfield cannot have items

    Or only subfields with items:

    >>> f = Field(2, 3, type="I")
    >>> f.value = [[1, 2]]
    >>> f.value = [1, 2]
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_SUBFIELD_VALUE: Subfield cannot have a value, only items
    >>> f.value = 'ok'
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_FIELD_VALUE: Field 2.003: cannot have a value (only subfields and/or items)

    Or subfields can be forbidden unless they have items:

    >>> f = Field(2, 3, type="FI")
    >>> f.add_subfields( SubField('a', type="SI") )
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_SUBFIELD_VALUE: Subfield of 2.003: cannot have a value: 'a'

    Or a subfield with items can be forbidden:

    >>> f = Field(2, 3, type="SF")
    >>> f.add_subfields( SubField(['a', 'b'], type="SI") )
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_SUBFIELD_VALUE: Subfield of 2.003: cannot have items

    """
    __slots__ = ['record', 'tag', 'type', 'format', 'alias', '_subfields', '_value']
    SEPARATOR = RS

    def __init__(self, record, tag, value='', type='FSI', format='%d.%03d:', alias=''):
        """
        Creation of a new field.

        - *record* indicates the record's type and must be an integer.
        - *tag* is the tag number and will be converted to an integer.
        - *value* the initial value. Must be a string or a list.
        - *type* indicates the possible type for the field content. It can be a
          combination of:

            - 'F': a single field, i.e. a simple value
            - 'S': this field can contain sub fields
            - 'I': this field can contain items
        - *format* is the format used to generate the tag number in the NIST.
        - *alias* is a name used as a shortcut when accessing the value.
        """
        self.record = record
        self.tag = int(tag)
        self.type = type
        self.format = format
        self.alias = alias
        self._subfields = []
        self._value = ''
        self.value = value

    def get_value(self):
        if self._subfields:
            return [x.value for x in self._subfields]
        return self._value
    def set_value(self, val):
        # if value is a list => create subfields
        self._value = ''
        self._subfields = []
        if not isinstance(val, (list, tuple)):
            if val and 'F' not in self.type:
                raise NistException("Field "+self.format% (self.record, self.tag)+" cannot have a value (only subfields and/or items)", NistError.BAD_FIELD_VALUE)
            self._value = val
            return
        if 'S' not in self.type and 'I' not in self.type:
            raise NistException("Field "+self.format% (self.record, self.tag)+" cannot have subfields", NistError.BAD_FIELD_VALUE)

        for v in val:
            if not isinstance(v, (list, tuple)):
                self.add_subfields(SubField(v, self.type))
            else:
                sf = SubField('', self.type)
                sf.add_values(*v)
                self.add_subfields(sf)

    value = property(get_value, set_value)
    """
    Access to the value of the field. The value is a string or a list
    of subfield values.

    """

    def __len__(self):
        """
        Return the number of subfields in the field.

        >>> f = Field(2, 3, ['one', 'two'])
        >>> print(len(f))
        2
        >>> f = Field(2, 21, "hello")
        >>> print(len(f))
        0
        """
        return len(self._subfields)

    def __getitem__(self, idx):
        """
        Access the *idx*-th sub field in the field.

        >>> f = Field(2, 3, ['one', 'two'])
        >>> print(f[0].value)
        one
        >>> print(f[1].value)
        two
        """
        return self._subfields[idx]

    def add_subfields(self, *sf):
        """
        Add a set of subfields to this field. Some consistency checks are run.
        """
        if sf and not ('S' in self.type or 'I' in self.type):
            raise NistException("Field "+self.format% (self.record, self.tag)+" cannot have subfields", NistError.BAD_FIELD_VALUE)
        self._value = ''
        for x in sf:
            if isinstance(x.value, (list, tuple)):
                if 'I' not in self.type:
                    raise NistException("Subfield of "+self.format% (self.record, self.tag)+" cannot have items", NistError.BAD_SUBFIELD_VALUE)
            else:
                if 'S' not in self.type:
                    raise NistException("Subfield of "+self.format% (self.record, self.tag)+" cannot have a value: "+repr(x.value), NistError.BAD_SUBFIELD_VALUE)
            x.type = self.type
            self._subfields.append(x)

    def reset(self):
        """
        Reset this field value and the list of subfields.
        """
        self._value = ''
        self._subfields = []

    @property
    def NIST(self):
        """
        Calculation of the NIST binary representation of this field.
        A bytes object is returned.

        If the value of the field is None, it is interpreted as an empty field.

        >>> f = Field(2, 2, None)
        >>> f.NIST
        b'2.002:'
        """
        begin = self.format % (self.record, self.tag)
        # This is standard text field, with possible subfields
        if not self._subfields:
            if self.value is None:
                return begin.encode('latin-1')
            s = begin+str(self.value)
            return s.encode('latin-1')
        return begin.encode('latin-1')+self.SEPARATOR.join([sf.NIST for sf in self._subfields])

#_______________________________________________________________________________
class BinaryField(object):
    """
    A binary field used as the last field in an :class:`AsciiRecord` record.

    """
    __slots__ = ['record', 'tag', '_value', 'format', 'alias']

    def __init__(self, record, tag, value=b'', format='%d.%03d:', alias=''):
        """
        Creation of a new binary field.

        - *record* indicates the record's type and must be an integer.
        - *tag* is the tag number and will be converted to an integer.
        - *value* the initial value. Must be a bytes object.
        - *format* is the format used to generate the tag number in the NIST.
        - *alias* is a name used as a shortcut when accessing the value.
        """
        self.record = record
        self.tag = int(tag)
        self._value = value
        self.format = format
        self.alias = alias

    def get_value(self):
        return self._value
    def set_value(self, val):
        self._value = val
    value = property(get_value, set_value)
    """
    Access to the value of the field. The value is a bytes object.
    """

    @property
    def NIST(self):
        """
        Calculation of the NIST binary representation of this field.
        A bytes object is returned.
        """
        begin = self.format % (self.record, self.tag)
        return begin.encode('latin-1')+self.value

#_______________________________________________________________________________
class SubField(object):
    """
    A SubField class, representing a subfield added to a :class:`Field`.

    A subfield can be typed to accept only items:

    >>> sf = SubField(type="I")
    >>> sf.value = ['a', 'b']
    >>> sf.value = 'error'
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_SUBFIELD_VALUE: Subfield cannot have a value, only items

    Or only a single value:

    >>> sf = SubField(type="S")
    >>> sf.value = 'ok'
    >>> sf.value = ['a', 'b']
    Traceback (most recent call last):
    ...
    nistitl.NistException: BAD_SUBFIELD_VALUE: Subfield cannot have items

    Or both:

    >>> sf = SubField(type="SI")
    >>> sf.value = 'ok'
    >>> sf.value = ['a', 'b']

    """
    __slots__ = ['_value', 'type', 'values']
    SEPARATOR = US

    def __init__(self, value='', type='SI'):
        """
        Creation of a new subfield.

        - *value* the initial value. Must be a string or a list of strings.
        - *type* indicates the possible type for the field content. It can be a
          combination of:

            - 'S': a single subfield, i.e. a simple value
            - 'I': this subfield can contain items
        """
        self._value = ''
        self.type = type
        self.values = []
        self.value = value

    def get_value(self):
        if 'I' in self.type and self.values:
            return self.values
        return self._value
    def set_value(self, val):
        self._value = ''
        self.values = []
        if not isinstance(val, (list, tuple)):
            if val and 'S' not in self.type:
                raise NistException("Subfield cannot have a value, only items", NistError.BAD_SUBFIELD_VALUE)
            self._value = val
            return
        self.add_values(*val)

    value = property(get_value, set_value)
    """
    Access to the value of the subfield. The value is a string or a list
    of strings.
    """

    def add_values(self, *i):
        """
        Add multiple values as items of this subfield.
        """
        if i and 'I' not in self.type:
            raise NistException("Subfield cannot have items", NistError.BAD_SUBFIELD_VALUE)
        for j in i:
            self.values.append(j)

    def __getitem__(self, idx):
        """
        Return th *idx*-th item.

        >>> sf = SubField(type="SI")
        >>> sf.value = ['a', 'b']
        >>> sf[0]
        'a'
        >>> sf[1]
        'b'
        """
        return self.values[idx]

    def __len__(self):
        """
        Return the number of items in the subfield.

        >>> f = SubField(type="I", value=['one', 'two'])
        >>> print(len(f))
        2
        """
        return len(self.values)

    @property
    def NIST(self):
        """
        Calculation of the NIST binary representation of this subfield.
        A bytes object is returned.

        If the value of the subfield is None, it is interpreted as an empty subfield.

        >>> sf = SubField(None)
        >>> sf.NIST
        b''

        If the value is not a string, it is converted to a string:

        >>> sf = SubField(12)
        >>> sf.NIST
        b'12'
        """
        if not self.values:
            if self.value is None:
                return b''
            if isinstance(self.value, int):
                return str(self.value).encode('latin-1')
            return self.value.encode('latin-1')
        return self.SEPARATOR.join([str(v).encode('latin-1') for v in self.values])

#_______________________________________________________________________________
# Some pre-defined aliases
ALIASES = {
    1: {
        1: 'LEN',
        2: 'VER',
        3: 'CNT',
        4: 'TOT',
        5: 'DAT',
        6: 'PRY',
        7: 'DAI',
        8: 'ORI',
        9: 'TCN',
        10: 'TCR',
        11: 'NSR',
        12: 'NTR',
        13: 'DOM',
        14: 'GMT',
        15: 'DCS',
    },
    2: {
        1: 'LEN',
        2: 'IDC',
    },
    9: {
        1: 'LEN',
        2: 'IDC',
    },
    10: {
        1: 'LEN',
        2: 'IDC',
        3: 'IMT',
        4: 'SRC',
        5: 'PHD',
        6: 'HLL',
        7: 'VLL',
        8: 'SLC',
        9: 'THPS',
        10: 'TVPS',
        11: 'CGA',
        12: 'CSP',
        13: 'SAP',
        14: 'FIP',
        15: 'FPFI',
        16: 'SHPS',
        17: 'SVPS',
        18: 'DIST',
        19: 'LAF',
        20: 'POS',
        21: 'POA',
        23: 'PAS',
        24: 'SQS',
        25: 'SPA',
        26: 'SXS',
        27: 'SEC',
        28: 'SHC',
        29: 'FFP',
        30: 'DMM',
        31: 'TMC',
        32: '3DF',
        33: 'FEC',
        34: 'ICDR',
        38: 'COM',
        39: 'T10',
        40: 'SMT',
        41: 'SMS',
        42: 'SMD',
        43: 'COL',
        44: 'ITX',
        45: 'OCC',
        46: 'SUB',
        47: 'CON',
        48: 'PID',
        49: 'CID',
        50: 'VID',
        51: 'RSP',
        902: 'ANN',
        903: 'DUI',
        904: 'MMS',
        992: 'T2C',
        993: 'SAN',
        994: 'EFR',
        995: 'ASC',
        996: 'HAS',
        997: 'SOR',
        998: 'GEO',
        999: 'DATA',
    },
    11: {
        1: 'LEN',
        2: 'IDC',
    },
    12: {
        1: 'LEN',
        2: 'IDC',
    },
    13: {
        1: 'LEN',
        2: 'IDC',
        3: 'IMP',
        4: 'SRC',
        5: 'LCD',
        6: 'HLL',
        7: 'VLL',
        8: 'SLC',
        9: 'THPS',
        10: 'TVPS',
        11: 'CGA',
        12: 'BPX',
        13: 'FGP',
        14: 'SPD',
        15: 'PPC',
        16: 'SHPS',
        17: 'SVPS',
        18: 'RSP',
        19: 'REM',
        20: 'COM',
        24: 'LQM',
        46: 'SUB',
        47: 'CON',
        901: 'FCT',
        902: 'ANN',
        903: 'DUI',
        904: 'MMS',
        992: 'T2C',
        993: 'SAN',
        994: 'EFR',
        995: 'ASC',
        996: 'HAS',
        997: 'SOR',
        998: 'GEO',
        999: 'DATA',
    },
    14: {
        1: 'LEN',
        2: 'IDC',
        3: 'IMP',
        4: 'SRC',
        5: 'FCD',
        6: 'HLL',
        7: 'VLL',
        8: 'SLC',
        9: 'THPS',
        10: 'TVPS',
        11: 'CGA',
        12: 'BPX',
        13: 'FGP',
        14: 'PPD',
        15: 'PPC',
        16: 'SHPS',
        17: 'SVPS',
        18: 'AMP',
        20: 'COM',
        21: 'SEG',
        22: 'NQM',
        23: 'SQM',
        24: 'FQM',
        25: 'ASEG',
        26: 'SCF',
        27: 'SIF',
        30: 'DMM',
        31: 'FAP',
        46: 'SUB',
        47: 'CON',
        901: 'FCT',
        902: 'ANN',
        903: 'DUI',
        904: 'MMS',
        993: 'SAN',
        994: 'EFR',
        995: 'ASC',
        996: 'HAS',
        997: 'SOR',
        998: 'GEO',
        999: 'DATA',

    },
    15: {
        1: 'LEN',
        2: 'IDC',
        4: 'SRC',
        6: 'HLL',
        7: 'VLL',
        9: 'THPS',
        10: 'TVPS',
        11: 'CGA',
        999: 'DATA',
    },
    16: {
        1: 'LEN',
        2: 'IDC',
        999: 'DATA',
    },
    17: {
        1: 'LEN',
        2: 'IDC',
        999: 'DATA',
    },
    18: {
        1: 'LEN',
        2: 'IDC',
    },
    19: {
        1: 'LEN',
        2: 'IDC',
        999: 'DATA',
    },
    20: {
        1: 'LEN',
        2: 'IDC',
        999: 'DATA',
    },
    21: {
        1: 'LEN',
        2: 'IDC',
        4: 'SRC',
        5: 'ACD',
        6: 'MDI',
        15: 'AFT',
        16: 'SEG',
        999: 'DATA',
    },
    22: {
        1: 'LEN',
        2: 'IDC',
        999: 'DATA',
    },
    98: {
        1: 'LEN',
        2: 'IDC',
    },
    99: {
        1: 'LEN',
        2: 'IDC',
        999: 'DATA',
    },
}
