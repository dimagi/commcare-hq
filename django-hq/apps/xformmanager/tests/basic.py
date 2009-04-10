from django.db import connection, transaction, DatabaseError
from xformmanager.tests.util import *

from datetime import datetime
import unittest

class BasicTestCase(unittest.TestCase):
    def setup(selfs):
        pass

    def testSaveFormData_1(self):
        """ Test basic form definition created and data saved """
        create_xsd_and_populate("1_xsd_basic.in", "1_xml_basic.in")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM x_xml_basic")
        row = cursor.fetchone()
        self.assertEquals(row[0],1)
        self.assertEquals(row[1],"userid0")
        self.assertEquals(row[2],"deviceid0")
        self.assertEquals(row[3],"starttime")
        self.assertEquals(row[4],"endtime")
        
    def testSaveFormData_2(self):
        """ Test basic form definition created and data saved.
            Currently only supported in MYSQL.
        """ 
        if settings.DATABASE_ENGINE=='mysql' :
            create_xsd_and_populate("2_xsd_types.in", "2_xml_types.in")
            cursor = connection.cursor()
            cursor.execute("DESCRIBE x_xml_types")
            row = cursor.fetchall()
            self.assertEquals(row[1][1],"varchar(255)")
            self.assertEquals(row[2][1],"int(11)")
            self.assertEquals(row[3][1],"int(11)")
            self.assertEquals(row[4][1],"decimal(5,2)")
            self.assertEquals(row[5][1],"int(11)")
            self.assertEquals(row[6][1],"double")
            self.assertEquals(row[7][1],"varchar(255)")
        else:
            pass
              
    
    def testSaveFormData_3(self):
        """ Test basic form definition created and data saved """
        create_xsd_and_populate("3_xsd_deep.in", "3_xml_deep.in")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM x_xml_deep")
        row = cursor.fetchone()
        self.assertEquals(row[1],"userid0")
        self.assertEquals(row[2],"abc")
        self.assertEquals(row[3],"xyz")
        self.assertEquals(row[4],222)
        self.assertEquals(row[5],"otherchild1")

    def testSaveFormData_4(self):
        """ Test basic form definition created and data saved """
        create_xsd_and_populate("4_xsd_verydeep.in", "4_xml_verydeep.in")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM x_xml_verydeep")
        row = cursor.fetchone()
        self.assertEquals(row[1],"userid0")
        self.assertEquals(row[2],"great_grand1")
        self.assertEquals(row[3],222)
        self.assertEquals(row[4],1159)
        self.assertEquals(row[5],2002)

    def testSaveFormData_5(self):
        """ Test basic form definition created and data saved """
        create_xsd_and_populate("5_xsd_singlerepeat.in", "5_xml_singlerepeat.in")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM x_xml_singlerepeat")
        row = cursor.fetchone()
        self.assertEquals(row[1],"deviceid0")
        self.assertEquals(row[2],"starttime")
        self.assertEquals(row[3],"endtime")
        cursor.execute("SELECT * FROM x_xml_singlerepeat_userid")
        row = cursor.fetchall()
        self.assertEquals(row[0][1],"userid0")
        self.assertEquals(row[1][1],"userid2")
        self.assertEquals(row[2][1],"userid3")
        self.assertEquals(row[0][2],1)
        self.assertEquals(row[1][2],1)
        self.assertEquals(row[2][2],1)

    def testSaveFormData_6(self):
        """ Test basic form definition created and data saved """
        create_xsd_and_populate("6_xsd_nestedrepeats.in", "6_xml_nestedrepeats.in")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM x_xml_nestedrepeats")
        row = cursor.fetchone()
        self.assertEquals(row[1],"foo")
        self.assertEquals(row[2],"bar")
        self.assertEquals(row[3],"yes")
        self.assertEquals(row[4],"no")
        cursor.execute("SELECT * FROM x_xml_nestedrepeats_meta")
        row = cursor.fetchall()
        self.assertEquals(row[0][1],"userid0")
        self.assertEquals(row[0][2],"deviceid0")
        self.assertEquals(row[0][3],"starttime")
        self.assertEquals(row[0][4],"endtime")
        self.assertEquals(row[0][5],1)
        self.assertEquals(row[1][1],"userid2")
        self.assertEquals(row[1][2],"deviceid2")
        self.assertEquals(row[1][3],"starttime2")
        self.assertEquals(row[1][4],"endtime2")
        self.assertEquals(row[1][5],1)
