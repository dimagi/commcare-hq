from xformmanager.tests.util import *
from xformmanager.xformdef import FormDef
from decimal import Decimal
from datetime import *
import unittest

class CompatibleTestCase(unittest.TestCase):
    def setUp(self):
        self.f1 = FormDef( get_file("data/versioning/base.xsd") )
        
    def testSame(self):
        """ Test FormDef.get_differences() """
        diff = self.f1.get_differences(self.f1)
        self.assertTrue(diff == None)

    def testAddAndRemove(self):
        """ Test FormDef.get_differences() """
        self.f1 = FormDef( get_file("data/versioning/base.xsd") )
        f2 = FormDef( get_file("data/versioning/field_added.xsd") )
        diff = self.f1.get_differences(f2)
        self.assertTrue(diff != None)
        self.assertTrue(len(diff.fields_added)==3)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==0)
        diff = f2.get_differences(self.f1)
        self.assertTrue(diff != None)
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==3)
        self.assertTrue(len(diff.fields_changed)==0)

    def testChangeEnumAddAndRemove(self):
        """ Test FormDef.get_differences() """
        f2 = FormDef( get_file("data/versioning/field_changed_enum.xsd") )
        diff = self.f1.get_differences(f2)
        self.assertTrue(diff != None)
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==1)
        diff = f2.get_differences(self.f1)
        self.assertTrue(diff != None)
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==1)

    def testChangeLeafRepeats(self):
        """ Test FormDef.get_differences() """
        # make repeatable
        f2 = FormDef( get_file("data/versioning/field_changed_repeatable_leaf.xsd") )
        diff = self.f1.get_differences(f2)
        self.assertTrue(diff != None)
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==1)
        # make not repeatable
        diff = f2.get_differences(self.f1)
        self.assertTrue(diff != None)
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==1)

    def testChangeNodeRepeats(self):
        """ Test FormDef.get_differences() """
        # make repeatable
        f1 = FormDef( get_file("data/versioning/repeats.xsd") )
        f2 = FormDef( get_file("data/versioning/field_changed_repeatable_node.xsd") )
        diff = f1.get_differences(f2)
        self.assertTrue(diff != None)
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==1)
        # make not repeatable
        diff = f2.get_differences(f1)
        self.assertTrue(diff != None)
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==1)

    def testChangeType(self):
        """ Test FormDef.get_differences() """
        f2 = FormDef( get_file("data/versioning/field_changed_type.xsd") )
        diff = self.f1.get_differences(f2)
        self.assertTrue(diff != None)
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==3)
