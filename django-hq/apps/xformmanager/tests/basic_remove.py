from django.db import connection, transaction, DatabaseError
from xformmanager.tests.util import *

from datetime import datetime
import unittest

class RemoveTestCase(unittest.TestCase):
    
    def test1ClearFormData(self):
        """ Tests clear out all forms. Only useful if run after all the other test cases """
        su = StorageUtility()
        su.clear()
        create_xsd_and_populate("1_basic.xsd", "1_basic.xml")
        create_xsd_and_populate("2_types.xsd", "2_types.xml")
        create_xsd_and_populate("3_deep.xsd", "3_deep.xml")
        create_xsd_and_populate("4_verydeep.xsd", "4_verydeep.xml")
        create_xsd_and_populate("5_singlerepeat.xsd", "5_singlerepeat.xml")
        create_xsd_and_populate("6_nestedrepeats.xsd", "6_nestedrepeats.xml")
        create_xsd_and_populate("data/pf_followup.xsd", "data/pf_followup_1.xml")
        su.clear()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_metadata")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'x\_%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)

    def test2RemoveSchema(self):
        """ Test removing one schema """
        su = StorageUtility()
        su.clear()
        schema_model = create_xsd_and_populate("1_basic.xsd", "1_basic.xml")
        su.remove_schema(schema_model.id)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'x_xml_basic%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)
    
    def test3RemoveSchema(self):
        """ Test removing one schema """
        su = StorageUtility()
        su.clear()
        schema_model = create_xsd_and_populate("6_nestedrepeats.xsd", "6_nestedrepeats.xml")
        su.remove_schema(schema_model.id)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'x_xml_basic%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)

