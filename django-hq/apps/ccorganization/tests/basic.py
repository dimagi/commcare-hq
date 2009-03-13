import unittest
from django.contrib.auth.models import Group, User

from ccorganization.models import *

class BasicTestCase(unittest.TestCase):
    def setup(selfs):
        pass

    def testCreateUserHierarchy(self):        
        pass
    def testFail(self):
        pass
        #self.assertFalse(False)

    def testSuccess(self):
        self.assertFalse(False)