import unittest
import traceback, sys, os
from xformmanager.tests.util import *

class UtilTestCase(unittest.TestCase):

    def testTranslateXFormToSchema(self):
        """ Test basic xform to schema translation"""
        fin = open(os.path.join(os.path.dirname(__file__),"basic.xform"),'r')
        (schema,err, has_error) = form_translate( fin.read() )
        if has_error:
            self.fail(err)
        
        
