from django.db import connection, transaction, DatabaseError
from xformmanager.tests.util import *

from datetime import datetime
import unittest

class RemoveTestCase(unittest.TestCase):
    def setup(selfs):
        pass

    def test1ClearFormData(self):
        """ Tests clear out all forms. Only useful if run after all the other test cases """
        su = StorageUtility()
        su.clear()
        create_xsd_and_populate("1_xsd_basic.in", "1_xml_basic.in")
        create_xsd_and_populate("2_xsd_types.in", "2_xml_types.in")
        create_xsd_and_populate("3_xsd_deep.in", "3_xml_deep.in")
        create_xsd_and_populate("4_xsd_verydeep.in", "4_xml_verydeep.in")
        create_xsd_and_populate("5_xsd_singlerepeat.in", "5_xml_singlerepeat.in")
        create_xsd_and_populate("6_xsd_nestedrepeats.in", "6_xml_nestedrepeats.in")
        su.clear()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefdata")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefdata")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'x\_%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)

    def test2RemoveSchema(self):
        """ Test removing one schema """
        schema_model = create_xsd_and_populate("1_xsd_basic.in", "1_xml_basic.in")
        su = StorageUtility()
        su.remove_schema(schema_model.id)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefdata")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefdata")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'x_xml_basic%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)
    
    def test3RemoveSchema(self):
        """ Test removing one schema """
        schema_model = create_xsd_and_populate("6_xsd_nestedrepeats.in", "6_xml_nestedrepeats.in")
        su = StorageUtility()
        su.remove_schema(schema_model.id)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefdata")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefdata")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'x_xml_basic%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)

