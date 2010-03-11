import unittest
import traceback, sys, os
from xformmanager.tests.util import *
from xformmanager.storageutility import Query, XFormDBTableCreator, XFormDBTablePopulator
from xformmanager.storageutility import StorageUtility as SU
from xformmanager.manager import XFormManager as XFM
from _mysql_exceptions import OperationalError, ProgrammingError
from receiver.models import Attachment

class UtilTestCase(unittest.TestCase):
            
    def testXFormErrors(self):
        """ Test proper reporting of poorly formed instance"""
        errors = self._testErrors( "data/util/xformerrors.xsd", "data/util/xformerrors.xml", "Errors" )
        self.assertTrue(len(errors.missing)==2)
        self.assertTrue(len(errors.bad_type)==2)

    def testXFormEmpty(self):
        """ Test proper reporting of empty instance"""
        errors = self._testErrors( "data/util/xformerrors.xsd", "data/util/xformempty.xml", "Empty" )
        self.assertTrue(len(errors.missing)==7)

    def testXFormNoErrors(self):
        """ Test proper reporting of good instance"""
        errors = self._testErrors( "data/util/xformerrors.xsd", "data/util/xformnoerrors.xml", "No Errors" )
        self.assertTrue(errors.is_empty())

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

    def _testErrors(self, schema_file, instance_file, id):
        su = SU()
        xfm = XFM()
        xsd_file_name = os.path.join(os.path.dirname(__file__),schema_file)
        xml_file_name = os.path.join(os.path.dirname(__file__),instance_file)

        schema = xfm._add_schema_from_file(xsd_file_name)
        formdef = su.get_formdef_from_schema_file(xsd_file_name)
        data_tree = su._get_data_tree_from_file(xml_file_name)
        populator = XFormDBTablePopulator( formdef, schema )
        queries = populator.populate( data_tree )
        xfm.remove_schema(schema.id)
        return populator.errors
        
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
