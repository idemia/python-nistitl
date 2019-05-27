

import unittest
import time
import sys
import struct

import nistitl
from nistitl import NistException

import io

NIST_OK = b"1.001:1271.002:04001.003:1221221.004:TOTFORTEST1.005:200909181.007:0001.008:0001.009:123451.011:00.001.012:00.002.001:452.002:12.012:TEST12-SF1TEST12-SF22.001:302.002:22.012:TEST12"
NIST_BAD_CNT = b"1.001:1231.002:04001.003:11211.004:TOTFORTEST1.005:200909181.007:0001.008:0001.009:123451.011:00.001.012:00.002.001:452.002:12.012:TEST12-SF1TEST12-SF22.001:302.002:22.012:TEST12"
#NIST_SYNTAX_ERROR = b"1.001:1232"

import os
IMAGE = os.path.join(os.path.split(__file__)[0],'portrait.jpg')

def PP(b):
    if b:
        return b.decode('latin-1')
    return u"None"

#_______________________________________________________________________________
class MyParser(object):
    def __init__(self):
        self.stream = io.StringIO()
    def __str__(self):
        return self.stream.getvalue()
    def pRecord(self):
        print(u'R', file=self.stream)
    def pRecordKO(self,value):
        print(u'R', file=self.stream)
    def pField(self,tag,value):
        if sys.version_info < (3,0):
            print(u'F',tag.decode('latin-1'),PP(value), file=self.stream)
        else:
            print(u'F',tag,PP(value), file=self.stream)
    def pFieldKO(self,tag):
        if sys.version_info < (3,0):
            print(u'F',tag.decode('latin-1'),PP(value), file=self.stream)
        else:
            print(u'F',tag,PP(value), file=self.stream)
    def pSubField(self,value):
        print(u'SF',PP(value), file=self.stream)
    def pSubFieldKO(self,value,value2):
        print(u'SF',PP(value), file=self.stream)
    def pValue(self,value):
        print(u'V',PP(value), file=self.stream)
    def pValueKO(self):
        print(u'V',PP(value), file=self.stream)
        
#_______________________________________________________________________________
class TestParseRawNist(unittest.TestCase):
    
    def testOK(self):
        self.maxDiff = None
        p = MyParser()
        self.assertEqual(nistitl.parse_record(NIST_BAD_CNT,p.pRecord,p.pField,p.pSubField,p.pValue),None)
        self.assertMultiLineEqual(str(p),"""F 1.001: 123
F 1.002: 0400
V 1
V 1
SF None
V 2
V 1
SF None
F 1.003: None
F 1.004: TOTFORTEST
F 1.005: 20090918
F 1.007: 000
F 1.008: 000
F 1.009: 12345
F 1.011: 00.00
F 1.012: 00.00
R
F 2.001: 45
F 2.002: 1
SF TEST12-SF1
SF TEST12-SF2
F 2.012: None
R
F 2.001: 30
F 2.002: 2
F 2.012: TEST12
R
""")

    def testSpeed(self):
        p = MyParser()
        t0 = time.time()
        for i in range(1000):
            self.assertTrue(nistitl.parse_record(NIST_OK,p.pRecord,p.pField,p.pSubField,p.pValue)==None)
        t1 = time.time()
##        print "Speed: %.3f ms" % ( (t1-t0),)
        self.assertTrue( (t1-t0)<0.5 )


    def testKO(self):
        p = MyParser()
        self.assertRaises(TypeError,nistitl.parse_record,NIST_OK,p.pRecordKO,p.pField,p.pSubField,p.pValue)
        self.assertRaises(TypeError,nistitl.parse_record,NIST_OK,p.pRecord,p.pFieldKO,p.pSubField,p.pValue)
        self.assertRaises(TypeError,nistitl.parse_record,NIST_OK,p.pRecord,p.pField,p.pSubFieldKO,p.pValue)
        self.assertRaises(TypeError,nistitl.parse_record,NIST_OK,p.pRecord,p.pField,p.pSubField,p.pValueKO)
#        self.assertRaises(nistitl.ParsingException,nistitl.parse_record,NIST_SYNTAX_ERROR,p.pRecord,p.pField,p.pSubField,p.pValue)

#_______________________________________________________________________________
class TestParseNist(unittest.TestCase):
    
    def testOK(self):
        msg = nistitl.Message()
        msg.parse(NIST_OK)
        self.assertTrue(msg.NIST==NIST_OK)
        
    def testKO(self):
        msg = nistitl.Message()
        self.assertRaises(NistException,msg.parse,NIST_BAD_CNT)

#_______________________________________________________________________________
class TestTaggedBinary(unittest.TestCase):
    
    def testOK(self):
        msg = nistitl.Message()
        msg.TOT = 'TESTTAGGEDBIN'

        r2 = nistitl.AsciiRecord(2)
        r2.IDC = 1
        msg += r2
        
        r10 = nistitl.AsciiRecord(10)
        r10.IDC = 1
        msg += r10
        
        f = open(IMAGE,'rb')
        buf = f.read()
        f.close()
        f999 = nistitl.BinaryField(10,999,buf)
        r10 += f999

        r10 = nistitl.AsciiRecord(10)
        r10.IDC = 2
        msg += r10
        
        f999 = nistitl.BinaryField(10,999,buf)
        r10 += f999
        
        #f = open('testtaggedbin.nist','wb')
        N = msg.NIST
        #f.write(N)
        #f.close()
        
        # parse the NIST
        msg = nistitl.Message()
        msg.parse(N)
        
        self.assertTrue(buf==msg[(10,1)][999].value)
        self.assertTrue(buf==msg[(10,2)][999].value)

#_______________________________________________________________________________
class TestBinary(unittest.TestCase):
    
    def testType10(self):
        f = open(IMAGE,'rb')
        buf = f.read()
        f.close()
        msg = nistitl.Message()
        msg.TOT = 'TESTBIN'

        r2 = nistitl.AsciiRecord(2)
        r2.IDC = 1
        msg += r2
        
        r4 = nistitl.BinaryRecord(4)
        r4.IDC = 1
        msg += r4
        r4.value = buf

        r10 = nistitl.AsciiRecord(10)
        r10.IDC = 1
        msg += r10
        f999 = nistitl.BinaryField(10,999,buf)
        r10 += f999

        N = msg.NIST
        
        # parse the NIST
        msg = nistitl.Message()
        msg.parse(N)
        
        self.assertEqual(len(msg[2].value),12911)
        self.assertTrue(buf==msg[2].value)

# XXX Test UTF-8 and encoding (1.015)

#_______________________________________________________________________________
class TestError(unittest.TestCase):
    
    def testOK(self):
        msg = nistitl.Message()
        msg.TOT = 'TESTBIN'

        # Two type 1
        r2 = nistitl.AsciiRecord(1)
        self.assertRaises(NistException,msg.__add__,r2)

        r2 = nistitl.AsciiRecord(2)
        r2 += nistitl.Field(2,3,alias='TT')
        self.assertRaises(NistException,r2.__add__, nistitl.Field(2,3) )
        self.assertRaises(NistException,r2.__add__, nistitl.Field(2,4,alias='TT') )
        self.assertRaises(NistException,r2.__add__, nistitl.Field(3,3) )
        
        f = nistitl.Field(2,99,type='F')
        f.value = "OK"
        self.assertRaises(NistException,f.add_subfields, nistitl.SubField() )
        f = nistitl.Field(2,99,type='FS')
        f.value = "OK"
        f.add_subfields(nistitl.SubField())
        self.assertRaises(NistException,f[0].add_values,"I" )
        
#_______________________________________________________________________________
class TestBug(unittest.TestCase):
    
    def testMaxSize(self):
        # Bug: syntax error when record length (parsable part) is over 8192
        msg = nistitl.Message()
        msg.TOT = 'TESTMAXSIZE'

        r2 = nistitl.AsciiRecord(2)
        r2.IDC = 1
        msg += r2
        f = nistitl.Field(2,3)
        f.value = [[1234,5678,345,'A']*600] #511]
        r2 += f

        r10 = nistitl.AsciiRecord(10)
        r10.IDC = 2
        msg += r10

        N = msg.NIST
        msg = nistitl.Message()
        msg.parse(N)
        

# ______________________________________________________________________________
if __name__=='__main__':
    unittest.main(argv=['-v'])
    
