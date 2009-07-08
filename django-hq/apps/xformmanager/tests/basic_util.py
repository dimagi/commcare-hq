import unittest
import traceback, sys, os
from xformmanager.tests.util import *

class BasicTestCase(unittest.TestCase):

    def testTranslateXFormToSchema(self):
        """ Test basic xform to schema translation"""
        fin = open(os.path.join(os.path.dirname(__file__),"basic.xform"),'r')
        (schema,err) = form_translate( "basic.xform", fin.read() )
        if err is not None:
            if err.lower().find("exception") != -1:
                self.fail(err)
        
        
