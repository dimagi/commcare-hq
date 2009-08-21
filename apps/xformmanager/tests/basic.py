from django.db import connection, transaction, DatabaseError
from xformmanager.tests.util import *

from decimal import Decimal
from datetime import *
import unittest

class BasicTestCase(unittest.TestCase):
    def setUp(self):
        su = StorageUtility()
        su.clear()
    
    def testSaveFormData_1(self):
        """ Test basic form definition created and data saved """
        create_xsd_and_populate("1_basic.xsd", "1_basic.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_basic")
        row = cursor.fetchone()
        self.assertEquals(row[0],1)
        self.assertEquals(row[5],"userid0")
        self.assertEquals(row[6],"deviceid0")
        self.assertEquals(row[7],"starttime")
        self.assertEquals(row[8],"endtime")
        
    def testSaveFormData_2(self):
        """ Test types created and data saved.
            Currently only supported in MYSQL.
        """ 
        cursor = connection.cursor()
        create_xsd_and_populate("2_types.xsd", "2_types.xml")
        if settings.DATABASE_ENGINE=='mysql' :
            cursor.execute("DESCRIBE schema_xml_types")
            row = cursor.fetchall()
            self.assertEquals(row[5][1],"varchar(255)")
            self.assertEquals(row[6][1],"int(11)")
            self.assertEquals(row[7][1],"int(11)")
            self.assertEquals(row[8][1],"decimal(5,2)")
            self.assertEquals(row[9][1],"double")            
            self.assertEquals(row[10][1],"date")
            self.assertEquals(row[11][1],"time")
            self.assertEquals(row[12][1],"datetime")
            self.assertEquals(row[13][1],"tinyint(1)")
            self.assertEquals(row[14][1],"tinyint(1)")
        else:
            pass
        cursor.execute("SELECT * FROM schema_xml_types")
        row = cursor.fetchone()
        self.assertEquals(row[5],"userid0")
        self.assertEquals(row[6],111)
        self.assertEquals(row[7],222)
        if settings.DATABASE_ENGINE=='mysql' :
            self.assertEquals(row[8],Decimal("3.20"))
        else:
            self.assertEquals( str(float(row[8])), "3.2" )
        self.assertEquals(row[9],2002.09)
        if settings.DATABASE_ENGINE=='mysql' :
            self.assertEquals(row[10],date(2002,9,24) )
            self.assertEquals(row[11],time(12,24,48))
            self.assertEquals(row[12],datetime(2007,12,31,23,59,59) )
        else:
            self.assertEquals(row[10],"2002-09-24" )
            self.assertEquals(row[11],"12:24:48")
            self.assertEquals(row[12],"2007-12-31 23:59:59" )
        self.assertEquals(row[13],None )
        self.assertEquals(row[14],None )
        self.assertEquals(row[15],1 )
        self.assertEquals(row[16],None )
        
        self.assertEquals(row[17],1 )
        self.assertEquals(row[18],None )
        self.assertEquals(row[19],1 )
        self.assertEquals(row[20],1 )
        
        self.assertEquals(row[21],None )
        self.assertEquals(row[22],None )
        self.assertEquals(row[23],None )
        self.assertEquals(row[24],None )
        
              
    
    def testSaveFormData_3(self):
        """ Test deep form definition created and data saved """
        create_xsd_and_populate("3_deep.xsd", "3_deep.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_deep")
        row = cursor.fetchone()
        self.assertEquals(row[5],"userid0")
        self.assertEquals(row[6],"abc")
        self.assertEquals(row[7],"xyz")
        self.assertEquals(row[8],222)
        self.assertEquals(row[9],"otherchild1")

    def testSaveFormData_4(self):
        """ Test very deep form definition created and data saved """
        create_xsd_and_populate("4_verydeep.xsd", "4_verydeep.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_verydeep")
        row = cursor.fetchone()
        self.assertEquals(row[5],"userid0")
        self.assertEquals(row[6],"great_grand1")
        self.assertEquals(row[7],222)
        self.assertEquals(row[8],1159)
        self.assertEquals(row[9],2002)

    def testSaveFormData_5(self):
        """ Test repeated form definition created and data saved """
        create_xsd_and_populate("5_singlerepeat.xsd", "5_singlerepeat.xml")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_xml_singlerepeat")
        row = cursor.fetchone()
        self.assertEquals(row[5],"deviceid0")
        self.assertEquals(row[6],"starttime")
        self.assertEquals(row[7],"endtime")
        cursor.execute("SELECT * FROM schema_xml_singlerepeat_userid")
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
        self.assertEquals(row[5],"foo")
        self.assertEquals(row[6],"bar")
        self.assertEquals(row[7],"yes")
        self.assertEquals(row[8],"no")
        cursor.execute("SELECT * FROM schema_xml_nestedrepeats_nested")
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
        self.assertEquals(edds[0].name,"UserID")
        self.assertEquals(edds[0].table_name,"schema_xml_singlerepeat_userid")
        
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
        self.assertEquals(edds[0].name,"nested")
        self.assertEquals(edds[0].table_name,"schema_xml_nestedrepeats_nested")
