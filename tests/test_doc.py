
import unittest
import doctest
import nistitl

# Used by: python setup.py test
def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(nistitl))
    return tests

load_tests.__test__ = False

# ______________________________________________________________________________
if __name__=='__main__':
    doctest.testmod(nistitl)
