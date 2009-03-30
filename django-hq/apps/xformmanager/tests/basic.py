from django.db import connection, transaction, DatabaseError
from xformmanager.xformdata import * 
from xformmanager.xformdef import *
from xformmanager.storageutility import *

from datetime import datetime
import unittest
import os

class BasicTestCase(unittest.TestCase):
    def setup(selfs):
        pass

    def testCreateFormDef(self):
        """ Test that form definitions are created correctly """
        self.__create_formdef("1_xsd_basic.in")

    def testSaveFormData_1(self):
        """ Test basic form definition created and data saved """
        self.__create_xsd_and_populate("1_xsd_basic.in", "1_xml_basic.in")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM x_xml_basic")
        row = cursor.fetchone()
        self.assertEquals(row[0],1)
        self.assertEquals(row[1],"userid0")
        self.assertEquals(row[2],"deviceid0")
        self.assertEquals(row[3],"starttime")
        self.assertEquals(row[4],"endtime")
        
    def testSaveFormData_2(self):
        """ Test basic form definition created and data saved - ONLY SUPPORTED IN MYSQL
        self.__create_xsd_and_populate("2_xsd_types.in", "2_xml_types.in")
        cursor = connection.cursor()
        cursor.execute("DESCRIBE xml_types")
        row = cursor.fetchall()
        self.assertEquals(row[1][1],"varchar(255)")
        self.assertEquals(row[2][1],"int(11)")
        self.assertEquals(row[3][1],"int(11)")
        self.assertEquals(row[4][1],"decimal(5,2)")
        self.assertEquals(row[5][1],"date")
        self.assertEquals(row[6][1],"double")
        self.assertEquals(row[7][1],"varchar(255)") """
    
    def testSaveFormData_3(self):
        """ Test basic form definition created and data saved """
        self.__create_xsd_and_populate("3_xsd_deep.in", "3_xml_deep.in")
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
        self.__create_xsd_and_populate("4_xsd_verydeep.in", "4_xml_verydeep.in")
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
        self.__create_xsd_and_populate("5_xsd_singlerepeat.in", "5_xml_singlerepeat.in")
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

    def testPopulate_1(self):
        """ Test basic form definition created and data saved
        self.__populate("1_xml_basic.in")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM x_xml_deep")
        rows = cursor.fetchone()
        self.assertTrue(  len(rows)== 2 )
        for row in rows:
            self.assertEquals(row[1],"userid0")
            self.assertEquals(row[2],"abc")
            self.assertEquals(row[3],"xyz")
            self.assertEquals(row[4],222)
            self.assertEquals(row[5],"otherchild1")        
        """

        # self.__create_xsd_and_populate("3_xsd_deep.in", "1_xml_deep.in")
        # self.__create_xsd_and_populate("4_xsd_singlerepeat.in", "1_xml_singlerepeat.in")
        # self.__create_xsd_and_populate("5_xsd_nestedrepeats.in", "1_xml_nestedrepeats.in")

    """ def testSaveData(self):
        # Test basic form definition created and data saved
        self.__populate("1_xsd_basic.in", "1_xml_basic.in")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xml_basic")
        row = cursor.fetchone()
        self.assertEquals(row[0],1)
        self.assertEquals(row['UserID'],"userid0")
        self.assertEquals(row['DevicID'],"deviceid0")
        self.assertEquals(row['TimeStartRecorded'],"starttime")
        self.assertEquals(row['TimeEndRecorded'],"endtime")
    """

    def __create_formdef(self, xsd_file_name):
        # Create a new form definition
        f = open( os.path.join(os.path.dirname(__file__),xsd_file_name),"r" )
        formDef = FormDef(f)
        print formDef.tostring()
        # see if output looks right
        f.close()
        pass
    
    def __create_xsd_and_populate(self, xsd_file_name, xml_file_name):
        # Create a new form definition
        su = StorageUtility()
        
        f = open(os.path.join(os.path.dirname(__file__),xsd_file_name),"r")
        formDef = FormDef(f)
        su.add_formdef(formDef)
        f.close()
        
        # and input one xml instance
        f = open(os.path.join(os.path.dirname(__file__),xml_file_name),"r")
        su.save_form_data_matching_formdef(f, formDef)
        # make sure tables are created the way you'd like
        f.close()
        
    def __populate(self, xml_file_name):
        # and input one xml instance
        su = StorageUtility()
        su.save_form_data( os.path.join(os.path.dirname(__file__),xml_file_name) )
        # make sure tables are created the way you'd like
