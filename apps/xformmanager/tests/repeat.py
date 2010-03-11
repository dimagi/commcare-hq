import unittest
from datetime import datetime
from django.db import connection
from xformmanager.tests.util import *

class RepeatTestCase(unittest.TestCase):
    
    def setUp(self):
        clear_data()
        mockdomain = Domain.objects.get_or_create(name='repeatdomain')[0]
        self.domain = mockdomain
        
        
    def testRepeatMultiples(self):
        """ Test multiple repeated form definition created and data saved """
        create_xsd_and_populate("data/repeat_multiple.xsd", "data/repeat_multiple.xml", self.domain)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_singlerepeat")
        row = cursor.fetchone()
        self.assertEquals(row[9],"starttime")
        self.assertEquals(row[10],"endtime")
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_singlerepeat_root_userid")
        row = cursor.fetchall()
        self.assertEquals(row[0][1],"userid0")
        self.assertEquals(row[1][1],"userid2")
        self.assertEquals(row[2][1],"userid3")
        self.assertEquals(row[0][2],1)
        self.assertEquals(row[1][2],1)
        self.assertEquals(row[2][2],1)
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_singlerepeat_root_my_device")
        row = cursor.fetchall()
        self.assertEquals(row[0][1],"deviceid0")
        self.assertEquals(row[1][1],"deviceid1")
        self.assertEquals(row[2][1],"deviceid2")
        self.assertEquals(row[0][2],1)
        self.assertEquals(row[1][2],1)
        self.assertEquals(row[2][2],1)

    def testRepeatNestedMultiples(self):
        """ Test multiple nested repeated form definition created and data saved """
        create_xsd_and_populate("data/repeat_nested_multiple.xsd", "data/repeat_nested_multiple.xml", self.domain)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_nestedrepeats")
        row = cursor.fetchone()
        self.assertEquals(row[9],"foo")
        self.assertEquals(row[10],"bar")
        self.assertEquals(row[11],"yes")
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_nestedrepeats_root_patient")
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
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_nestedrepeats_root_nurse")
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

