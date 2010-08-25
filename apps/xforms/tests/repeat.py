import unittest
from datetime import datetime
from django.conf import settings
from django.db import connection
from corehq.apps.domain.models import Domain
from xforms.tests.util import clear_data, create_xsd_and_populate, populate
from corehq.util.dbutils import is_configured_realsql, is_configured_postgres, is_configured_mysql

class RepeatTestCase(unittest.TestCase):
    
    def setUp(self):
        clear_data()
        mockdomain = Domain.objects.get_or_create(name='repeatdomain')[0]
        self.domain = mockdomain
        
        
    def testRepeatMultiples(self):
        """ Test multiple repeated form definition created and data saved """
        create_xsd_and_populate("data/repeat_multiple.xsd", "data/repeat_multiple_1.xml", self.domain)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_singlerepeat")
        rows = cursor.fetchall()
        self.assertEqual(1, len(rows))
        row = rows[0]
        row_id = row[0]
        self.assertEquals(1, row_id)
        self.assertEquals(row[9],"starttime")
        self.assertEquals(row[10],"endtime")
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_singlerepeat_root_userid")
        row = cursor.fetchall()
        self.assertEquals(row[0][1],"userid0")
        self.assertEquals(row[1][1],"userid2")
        self.assertEquals(row[2][1],"userid3")
        self.assertEquals(row[0][2],row_id)
        self.assertEquals(row[1][2],row_id)
        self.assertEquals(row[2][2],row_id)
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_singlerepeat_root_my_device")
        row = cursor.fetchall()
        self.assertEquals(row[0][1],"deviceid0")
        self.assertEquals(row[1][1],"deviceid1")
        self.assertEquals(row[2][1],"deviceid2")
        self.assertEquals(row[0][2],row_id)
        self.assertEquals(row[1][2],row_id)
        self.assertEquals(row[2][2],row_id)
        # test a second repeat to make sure child ids link correctly
        populate("data/repeat_multiple_2.xml", self.domain)
        cursor.execute("SELECT distinct parent_id FROM schema_repeatdomain_xml_singlerepeat_root_my_device")
        rows= cursor.fetchall()
        self.assertEqual(2, len(rows))
        ids = [row[0] for row in rows]
        self.assertTrue(1 in ids)
        self.assertTrue(2 in ids)
        cursor.execute("SELECT * FROM schema_repeatdomain_xml_singlerepeat_root_my_device where parent_id=2")
        rows = cursor.fetchall()
        self.assertEqual(3, len(rows))
        for row in rows:
            self.assertTrue(row[1].startswith("second"))
        
        
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
        if is_configured_postgres():
            self.assertEquals(row[0][3],datetime(2009,10,9,11,4,30,300000) )
            self.assertEquals(row[0][4],datetime(2009,10,9,11,9,30,300000) )
        elif is_configured_mysql():
            self.assertEquals(row[0][3],datetime(2009,10,9,11,4,30) )
            self.assertEquals(row[0][4],datetime(2009,10,9,11,9,30) )
        else:
            self.assertEquals(row[0][3],"2009-10-9 11:04:30" )
            self.assertEquals(row[0][4],"2009-10-9 11:09:30" )
        self.assertEquals(row[0][5],1)
        self.assertEquals(row[1][1],"userid2")
        self.assertEquals(row[1][2],"deviceid2")
        if is_configured_realsql():
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
        if is_configured_postgres():
            self.assertEquals(row[0][3],datetime(2009,10,9,11,4,30,300000) )
            self.assertEquals(row[0][4],datetime(2009,10,9,11,9,30,300000) )
        elif is_configured_mysql():
            self.assertEquals(row[0][3],datetime(2009,10,9,11,4,30) )
            self.assertEquals(row[0][4],datetime(2009,10,9,11,9,30) )
        else:
            self.assertEquals(row[0][3],"2009-10-9 11:04:30" )
            self.assertEquals(row[0][4],"2009-10-9 11:09:30" )
        self.assertEquals(row[0][5],1)
        self.assertEquals(row[1][1],"userid2")
        self.assertEquals(row[1][2],"deviceid2")
        if is_configured_realsql():
            self.assertEquals(row[1][3],datetime(2009,11,12,11,11,11) )
            self.assertEquals(row[1][4],datetime(2009,11,12,11,16,11) )
        else:
            self.assertEquals(row[1][3],"2009-11-12 11:11:11" )
            self.assertEquals(row[1][4],"2009-11-12 11:16:11" )
        self.assertEquals(row[1][5],1)

