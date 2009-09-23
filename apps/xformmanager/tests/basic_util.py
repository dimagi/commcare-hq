import unittest
import traceback, sys, os
from xformmanager.tests.util import *
from _mysql_exceptions import OperationalError, ProgrammingError

class UtilTestCase(unittest.TestCase):
            
    def testTranslateXFormToSchema(self):
        """ Test basic xform to schema translation"""
        fin = open(os.path.join(os.path.dirname(__file__),"basic.xform"),'r')
        (schema,err, has_error) = form_translate( fin.read() )
        if has_error:
            self.fail(err)
        
    def testTranslateVersionedXFormToSchema(self):
        """ Test basic xform to schema translation"""
        fin = open(os.path.join(os.path.dirname(__file__),"basic_versioned.xform"),'r')
        (schema,err, has_error) = form_translate( fin.read() )
        if has_error:
            self.fail(err)
    
    """  Currently fails on MyISAM
    def testTransactionManaged(self):
        # Test for transaction management
        try:
            # register a known bad schema
            create_xsd_and_populate("data/dupe_select_values.xml")
        except OperationalError, e:
            # we expect 'Duplicate column name 'brac_treated_mosquito_nets_n'
            self.assertTrue(unicode(e).lower().find('duplicate')!=-1)

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM schema_dupe_select_values")
        except ProgrammingError, e:
            # we expect 'Table 'test_commcarehq.schema_xml_basic' doesn't exist'
            self.assertTrue(unicode(e).lower().find("doesn't exist")!=-1)
        
        try:
            FormDefModel.objects.get(form_name='schema_dupe_select_values')
            # this is where things currently fail with MyISAM
            self.fail("Formdefmodel dupe_select_values should NOT be created")
        except FormDefModel.DoesNotExist:
            pass
    """
