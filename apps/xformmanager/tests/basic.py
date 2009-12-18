from django.db import connection, transaction, DatabaseError
from xformmanager.tests.util import *
from xformmanager.models import FormDefModel

from decimal import Decimal
from datetime import *
import unittest

class BasicTestCase(unittest.TestCase):
    
    def setUp(self):
        clear_data()
        
    def testSaveFormData_1(self):
        """ Test basic form definition created and data saved """
        create_xsd_and_populate("1_basic.xsd", "1_basic.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_basic")
        row = cursor.fetchone()
        self.assertEquals(row[0],1)
        self.assertEquals(row[9],"userid0")
        self.assertEquals(row[10],"deviceid0")
        self.assertEquals(row[11],"starttime")
        self.assertEquals(row[12],"endtime")
        
    def testSaveFormData_2(self):
        """ Test types created and data saved.
            Currently only supported in MYSQL.
        """ 
        cursor = connection.cursor()
        create_xsd_and_populate("2_types.xsd", "2_types.xml")
        if settings.DATABASE_ENGINE=='mysql' :
            cursor.execute("DESCRIBE schema_xml_types")
            row = cursor.fetchall()
            self.assertEquals(row[9][1],"varchar(255)")
            self.assertEquals(row[10][1],"int(11)")
            self.assertEquals(row[11][1],"int(11)")
            self.assertEquals(row[12][1],"decimal(5,2)")
            self.assertEquals(row[13][1],"double")            
            self.assertEquals(row[14][1],"date")
            self.assertEquals(row[15][1],"time")
            self.assertEquals(row[16][1],"datetime")
            self.assertEquals(row[17][1],"tinyint(1)")
            self.assertEquals(row[18][1],"tinyint(1)")
        else:
            pass
        cursor.execute("SELECT * FROM schema_xml_types")
        row = cursor.fetchone()
        self.assertEquals(row[9],"userid0")
        self.assertEquals(row[10],111)
        self.assertEquals(row[11],222)
        if settings.DATABASE_ENGINE=='mysql' :
            self.assertEquals(row[12],Decimal("3.20"))
        else:
            self.assertEquals( str(float(row[8])), "3.2" )
        self.assertEquals(row[13],2002.09)
        if settings.DATABASE_ENGINE=='mysql' :
            self.assertEquals(row[14],date(2002,9,24) )
            self.assertEquals(row[15],time(12,24,48))
            self.assertEquals(row[16],datetime(2007,12,31,23,59,59) )
        else:
            self.assertEquals(row[14],"2002-09-24" )
            self.assertEquals(row[15],"12:24:48")
            self.assertEquals(row[16],"2007-12-31 23:59:59" )
        self.assertEquals(row[17],None )
        self.assertEquals(row[18],None )
        self.assertEquals(row[19],1 )
        self.assertEquals(row[20],None )
        
        self.assertEquals(row[21],1 )
        self.assertEquals(row[22],None )
        self.assertEquals(row[23],1 )
        self.assertEquals(row[24],1 )
        
        self.assertEquals(row[25],None )
        self.assertEquals(row[26],None )
        self.assertEquals(row[27],None )
        self.assertEquals(row[28],None )
        

    
    def testSaveFormData_3(self):
        """ Test deep form definition created and data saved """
        create_xsd_and_populate("3_deep.xsd", "3_deep.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_deep")
        row = cursor.fetchone()
        self.assertEquals(row[9],"userid0")
        self.assertEquals(row[10],"abc")
        self.assertEquals(row[11],"xyz")
        self.assertEquals(row[12],222)
        self.assertEquals(row[13],"otherchild1")

    def testSaveFormData_4(self):
        """ Test very deep form definition created and data saved """
        create_xsd_and_populate("4_verydeep.xsd", "4_verydeep.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_verydeep")
        row = cursor.fetchone()
        self.assertEquals(row[9],"userid0")
        self.assertEquals(row[10],"great_grand1")
        self.assertEquals(row[11],222)
        self.assertEquals(row[12],1159)
        self.assertEquals(row[13],2002)

    def testSaveFormData_5(self):
        """ Test repeated form definition created and data saved """
        create_xsd_and_populate("5_singlerepeat.xsd", "5_singlerepeat.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_singlerepeat")
        row = cursor.fetchone()
        self.assertEquals(row[9],"deviceid0")
        self.assertEquals(row[10],"starttime")
        self.assertEquals(row[11],"endtime")
        cursor.execute("SELECT * FROM schema_xml_singlerepeat_root_userid")
        row = cursor.fetchall()
        self.assertEquals(row[0][1],"userid0")
        self.assertEquals(row[1][1],"userid2")
        self.assertEquals(row[2][1],"userid3")
        self.assertEquals(row[0][2],1)
        self.assertEquals(row[1][2],1)
        self.assertEquals(row[2][2],1)

    def testSaveFormData_6(self):
        """ Test nested repeated form definition created and data saved """
        create_xsd_and_populate("6_nestedrepeats.xsd", "6_nestedrepeats.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_nestedrepeats")
        row = cursor.fetchone()
        self.assertEquals(row[9],"foo")
        self.assertEquals(row[10],"bar")
        self.assertEquals(row[11],"yes")
        self.assertEquals(row[12],"no")
        cursor.execute("SELECT * FROM schema_xml_nestedrepeats_root_nested")
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

    def testSaveFormData_BasicFormAndElementDefModels(self):
        """ Test that the correct child/parent ids and tables are created """
        create_xsd_and_populate("5_singlerepeat.xsd", "5_singlerepeat.xml")
        create_xsd_and_populate("6_nestedrepeats.xsd", "6_nestedrepeats.xml")
        fd = FormDefModel.objects.get(form_name="schema_xml_singlerepeat")
        # test the children tables are generated with the correct parent
        edds = ElementDefModel.objects.filter(form=fd)
        self.assertEquals(len(edds),2)
        # test that the top elementdefmodel has itself as a parent
        top_edm = ElementDefModel.objects.get(id=fd.element.id)
        self.assertEquals(top_edm.parent, top_edm)
        # test that table name is correct
        self.assertEquals(top_edm.table_name, "schema_xml_singlerepeat")
        # test for only one child table
        edds = ElementDefModel.objects.filter(parent=top_edm).exclude(id=top_edm.id)
        self.assertEquals(len(edds),1)
        # test that that child table's parent is 'top'
        self.assertEquals(edds[0].parent,top_edm)
        self.assertEquals(edds[0].xpath,"root/UserID")
        self.assertEquals(edds[0].table_name,"schema_xml_singlerepeat_root_userid")
        
        # do it all again for a second table (to make sure counts are right)
        fd = FormDefModel.objects.get(form_name="schema_xml_nestedrepeats")
        edds = ElementDefModel.objects.filter(form=fd)
        self.assertEquals(len(edds),2)
        top_edm = ElementDefModel.objects.get(id=fd.element.id)
        self.assertEquals(top_edm.parent, top_edm)
        self.assertEquals(top_edm.table_name, "schema_xml_nestedrepeats")
        edds = ElementDefModel.objects.filter(parent=top_edm).exclude(id=top_edm.id)
        self.assertEquals(len(edds),1)
        self.assertEquals(edds[0].parent,top_edm)
        self.assertEquals(edds[0].xpath,"root/nested")
        self.assertEquals(edds[0].table_name,"schema_xml_nestedrepeats_root_nested")

    def testGetFormDef(self):
        """ Test get_formdef """
        create_xsd_and_populate("5_singlerepeat.xsd")
        create_xsd_and_populate("data/8_singlerepeat_2.xsd")
        formdef = FormDefModel.get_formdef("xml_singlerepeat")
        self.assertTrue(formdef.version is None)
        self.assertTrue(formdef.uiversion is None)
        self.assertEqual(len(formdef.root.child_elements), 5)
        formdef2 = FormDefModel.get_formdef("xml_singlerepeat", "2")
        self.assertTrue(formdef2.version == 2)
        self.assertTrue(formdef2.uiversion == 3)
        self.assertEqual(len(formdef2.root.child_elements), 5)
        nonexistant = FormDefModel.get_formdef("nonexistent", "1")
        self.assertTrue(nonexistant is None)
    
    def isSchemaRegistered(self):
        """ given a form and version is that form registered """
        create_xsd_and_populate("5_singlerepeat.xsd")
        create_xsd_and_populate("data/8_singlerepeat_2.xsd")
        self.assertTrue(FormDefModel.is_schema_registered("xml_singlerepeat"))
        self.assertTrue(FormDefModel.is_schema_registered("xml_singlerepeat",2))
        self.assertFalse(FormDefModel.is_schema_registered("xml_singlerepeat",3))
        self.assertFalse(FormDefModel.is_schema_registered("nonexistent",1))
