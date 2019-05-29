
import unittest
import nistitl

#_______________________________________________________________________________
class TestReadme(unittest.TestCase):
    
    def testGenerate(self):
        msg = nistitl.Message()
        msg.TOT = 'MY_TOT'

        r2 = nistitl.AsciiRecord(2)
        r2 += nistitl.Field(2,3,alias='TEST')
        msg += r2

        buffer = msg.NIST

        self.assertTrue(len(msg.NIST)>10)
        
        msg = nistitl.Message()
        msg.parse(buffer)
        print("The TOT is ",msg.TOT)
        for record in msg.iter(2):
            print("Field 2.003 is ",record._3)

# ______________________________________________________________________________
if __name__=='__main__':
    unittest.main(argv=['-v'])
    
