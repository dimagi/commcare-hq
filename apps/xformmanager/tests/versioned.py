from django.db import connection, transaction, DatabaseError
from xformmanager.tests.util import *
from xformmanager.xformdef import FormDef
from xformmanager.manager import XFormManager
from decimal import Decimal
from datetime import *
import unittest

class VersionedTestCase(unittest.TestCase):
    def setUp(self):
        su = StorageUtility()
        su.clear()

    def testFormDef_7(self):
        """ Test deep form definition created and data saved """
        fin = open( getfile("7_verydeep_2.xsd"), 'r' )
        formdef = FormDef(fin)
        fin.close()
        root = formdef.root
        self.assertEqual(formdef.target_namespace, "xml_verydeep")
        self.assertEqual(formdef.version, "1")
        self.assertEqual(root.xpath, "root")
        self.assertEqual(root.child_elements[0].xpath, "root/Meta")
        self.assertEqual(root.child_elements[0].child_elements[0].xpath, "root/Meta/formName")

    def testSaveFormData_7(self):
        """ Test very deep form definition created and data saved """
        formdefmodel = create_xsd_and_populate("7_verydeep_2.xsd", "7_verydeep_2.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_verydeep_1")
        row = cursor.fetchone()
        try:
            self.assertEquals(row[9],"userid0")
            self.assertEquals(row[10],"great_grand1")
            self.assertEquals(row[11],222)
            self.assertEquals(row[12],1159)
            self.assertEquals(row[13],2002)
        finally:
            manager = XFormManager()
            manager.remove_schema(formdefmodel.id)

    def testSaveFormData_8(self):
        """ Test repeated form definition created and data saved """
        formdefmodel = create_xsd_and_populate("8_singlerepeat_2.xsd", "8_singlerepeat_2.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_singlerepeat_2")
        try:
            row = cursor.fetchone()
            self.assertEquals(row[9],"deviceid0")
            self.assertEquals(row[10],"starttime")
            self.assertEquals(row[11],"endtime")
            cursor.execute("SELECT * FROM schema_xml_singlerepeat_root_userid_2")
            row = cursor.fetchall()
            self.assertEquals(row[0][1],"userid0")
            self.assertEquals(row[1][1],"userid2")
            self.assertEquals(row[2][1],"userid3")
            self.assertEquals(row[0][2],1)
            self.assertEquals(row[1][2],1)
            self.assertEquals(row[2][2],1)
        finally:
            manager = XFormManager()
            manager.remove_schema(formdefmodel.id)

    def testSaveFormData_9(self):
        """ Test nested repeated form definition created and data saved """
        formdefmodel = create_xsd_and_populate("6_nestedrepeats.xsd", "6_nestedrepeats.xml")
        formdefmodel_2 = create_xsd_and_populate("9_nestedrepeats_2.xsd", "9_nestedrepeats_2.xml")
        formdefmodel_3 = create_xsd_and_populate("9_nestedrepeats_3.xsd", "9_nestedrepeats_3.xml")
        formdefmodel_4 = create_xsd_and_populate("9_nestedrepeats_4.xsd", "9_nestedrepeats_4.xml")
        try:
            for i in (2,3,4):
                cursor = connection.cursor()
                cursor.execute("SELECT * FROM schema_xml_nestedrepeats_%s" % i)
                row = cursor.fetchone()
                self.assertEquals(row[9],"foo")
                self.assertEquals(row[10],"bar")
                self.assertEquals(row[11],"yes")
                self.assertEquals(row[12],"no")
                cursor.execute("SELECT * FROM schema_xml_nestedrepeats_root_nested_%s" % i)
                row = cursor.fetchall()
                self.assertEquals(row[0][1],"userid0")
                self.assertEquals(row[0][2],"deviceid0")
                if settings.DATABASE_ENGINE=='mysql' :
                    self.assertEquals(row[0][3],datetime(2009,10,9,11,4,30) )
                    self.assertEquals(row[0][4],datetime(2009,10,9,11,9,30) )
                else:
                    self.assertEquals(row[0][3],"2009-10-9 11:04:30" )
                    self.assertEquals(row[0][4],"2009-10-9 11:09:30" )
                self.assertEquals(row[0][5],1)
                self.assertEquals(row[1][1],"userid2")
                self.assertEquals(row[1][2],"deviceid2")
                if settings.DATABASE_ENGINE=='mysql' :
                    self.assertEquals(row[1][3],datetime(2009,11,12,11,11,11) )
                    self.assertEquals(row[1][4],datetime(2009,11,12,11,16,11) )
                else:
                    self.assertEquals(row[1][3],"2009-11-12 11:11:11" )
                    self.assertEquals(row[1][4],"2009-11-12 11:16:11" )
                self.assertEquals(row[1][5],1)
        finally:
            manager = XFormManager()
            manager.remove_schema(formdefmodel.id)
            manager.remove_schema(formdefmodel_2.id)
            manager.remove_schema(formdefmodel_3.id)
            manager.remove_schema(formdefmodel_4.id)
    

def getfile(filename, path=None ):
    if not path:
        path = os.path.dirname(__file__)
    return os.path.join( path, filename )

