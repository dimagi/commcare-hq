from xformmanager.tests.util import *
from xformmanager.xformdef import FormDef
from decimal import Decimal
from datetime import *
import unittest

class CompatibleTestCase(unittest.TestCase):
    def setUp(self):
        self.f1 = FormDef.from_file( get_file("data/versioning/base.xsd") )
        
    def testSame(self):
        """ testSame """
        diff = self.f1.get_differences(self.f1)
        self.assertTrue(diff.is_empty())

    def testAddAndRemove(self):
        """ testAddAndRemove """
        self.f1 = FormDef.from_file( get_file("data/versioning/base.xsd") )
        f2 = FormDef.from_file( get_file("data/versioning/field_added.xsd") )
        diff = self.f1.get_differences(f2)
        self.assertFalse(diff.is_empty())
        self.assertTrue(len(diff.fields_added)==3)
        self.assertTrue(len(diff.fields_changed)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        diff = f2.get_differences(self.f1)
        self.assertFalse(diff.is_empty())
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==3)
        self.assertTrue(len(diff.fields_changed)==0)

    def testChangeEnumAddAndRemove(self):
        """ testChangeEnumAddAndRemove """
        f2 = FormDef.from_file( get_file("data/versioning/field_changed_enum.xsd") )
        diff = self.f1.get_differences(f2)
        self.assertFalse(diff.is_empty())
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_changed)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.types_changed)==1)
        diff = f2.get_differences(self.f1)
        self.assertFalse(diff.is_empty())
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_changed)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.types_changed)==1)

    def testChangeLeafRepeats(self):
        """ testChangeLeafRepeats """
        # make repeatable
        f2 = FormDef.from_file( get_file("data/versioning/field_changed_repeatable_leaf.xsd") )
        diff = self.f1.get_differences(f2)
        self.assertFalse(diff.is_empty())
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==1)
        # make not repeatable
        diff = f2.get_differences(self.f1)
        self.assertFalse(diff.is_empty())
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==1)

    def testChangeNodeRepeats(self):
        """ testChangeNodeRepeats """
        # make repeatable
        f1 = FormDef.from_file( get_file("data/versioning/repeats.xsd") )
        f2 = FormDef.from_file( get_file("data/versioning/field_changed_repeatable_node.xsd") )
        diff = f1.get_differences(f2)
        self.assertFalse(diff.is_empty())
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        # when the parent becomes repeatable, both parent and child have changed
        self.assertTrue(len(diff.fields_changed)==2)
        # make not repeatable
        diff = f2.get_differences(f1)
        self.assertFalse(diff.is_empty())
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        # when the parent becomes repeatable, both parent and child have changed
        self.assertTrue(len(diff.fields_changed)==2)

    def testChangeType(self):
        """ testChangeType """
        f2 = FormDef.from_file( get_file("data/versioning/field_changed_type.xsd") )
        diff = self.f1.get_differences(f2)
        self.assertFalse(diff.is_empty())
        self.assertTrue(len(diff.fields_added)==0)
        self.assertTrue(len(diff.fields_removed)==0)
        self.assertTrue(len(diff.fields_changed)==3)
