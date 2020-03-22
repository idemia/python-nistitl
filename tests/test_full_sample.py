
import unittest
import nistitl

#_______________________________________________________________________________
class TestFull(unittest.TestCase):
    
    def test_full(self):
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
        r4.pack("!HH", 500, 500, b'image')

        # --- Add a type 10 record
        r10 = nistitl.AsciiRecord(10)
        msg += r10
        r10.IDC = 3
        # Used pre-defined alias
        r10.SRC = 'my src'
        r10.DATA = b'image'

        # Generate the NIST buffer
        buffer = msg.NIST

        self.assertTrue(len(buffer)>10)

        # ---------------------------------------------------------------------

        msg = nistitl.Message()
        msg.parse(buffer)

        # --- Access type 2 record
        r2 = msg[(2, 1)]
        # Read field 2.003
        v = r2._3

        # --- Loop on all records of type 4
        for r4 in msg.iter(4):
            # Get all fields
            width, height, data = r4.unpack("!HH")

        # --- Loop on all records of type 10
        for r10 in msg.iter(10):
            # Used pre-defined alias
            src = r10.SRC
            image = r10.DATA

# ______________________________________________________________________________
if __name__=='__main__':
    unittest.main(argv=['-v'])
    
