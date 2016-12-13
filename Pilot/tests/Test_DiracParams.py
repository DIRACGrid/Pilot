"""Unit tests for DiracParams
"""

import unittest
from Pilot.DiracParams import Params

class TestDiractParams( unittest.TestCase ):
  """ Base class for tests """

  def setUp( self ):
    """ Set up """
    pass

  def tearDown( self ):
    """ Tear down """
    pass

  def test_instanciate(self):
    """ Test correct instanations"""
    myParams = Params()
    self.assertEquals(myParams.installation,  "DIRAC")


if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( TestDiractParams )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )
