from django.db import connection

from xforms.tests.util import clear_data, create_xsd_and_populate, populate

import os
import unittest
from corehq.util.test import replace_in_file
from domain.models import Domain

LAT = 10.001666666666667
LON = 11.001666666666667
ALT = 0.0
ACC = 0.1

class BasicTestCase(unittest.TestCase):
    
    def setUp(self):
        clear_data()
        mockdomain = Domain.objects.get_or_create(name='geodomain')[0]
        self.instance_filename = os.path.join(os.path.dirname(__file__),
                                              "data", "geopoint", "geopoint_instance.xml")
        self.domain = mockdomain
    
    def testSaveGeoFormData(self):
        """Test form definition with geopoint"""
        filename = replace_in_file(self.instance_filename, "REPLACE_ME", 
                                   "%s %s %s %s" % (LAT, LON, ALT, ACC))
        create_xsd_and_populate("data/geopoint/geopoint_form.xhtml",
                                filename,
                                self.domain)
        self._check_row()
        
    
    def testSaveGeoFormDataFromXsd(self):
        """Test form definition with geopoint"""
        filename = replace_in_file(self.instance_filename, "REPLACE_ME", 
                                   "%s %s %s %s" % (LAT, LON, ALT, ACC))
        create_xsd_and_populate("data/geopoint/geopoint_form.xsd",
                                filename,
                                self.domain)
        self._check_row()
        
    
    def testSaveGeoDataNoNode(self):
        """Test form definition with geopoint - no submitted data"""
        filename = replace_in_file(self.instance_filename, 
                                   "<GPSCOORDS_data>REPLACE_ME</GPSCOORDS_data>", 
                                   "")
        create_xsd_and_populate("data/geopoint/geopoint_form.xhtml",
                                filename,
                                self.domain)
        self._check_row(None, None, None, None)
        

    def testSaveGeoDataMissingFields(self):
        """Test form definition with geopoint - EXTRA FIELDS"""
        filename = replace_in_file(self.instance_filename, "REPLACE_ME", 
                                   "%s" % (LAT))
        create_xsd_and_populate("data/geopoint/geopoint_form.xhtml",
                                filename,
                                self.domain)
        self._check_row(LAT, None, None, None)
        
        filename = replace_in_file(self.instance_filename, "REPLACE_ME", 
                                   "%s %s" % (LAT, LON))
        populate(filename, self.domain)
        self._check_row(LAT, LON, None, None)
        
        filename = replace_in_file(self.instance_filename, "REPLACE_ME", 
                                   "%s %s %s" % (LAT, LON, ALT))
        populate(filename, self.domain)
        self._check_row(LAT, LON, ALT, None)
        
    def testSaveExtraValues(self):
        """Test form definition with geopoint"""
        filename = replace_in_file(self.instance_filename, "REPLACE_ME", 
                                   "%s %s %s %s %s" % (LAT, LON, ALT, ACC, "0.211"))
        
        # unfortunately this doesn't fail hard, so we just check for the 
        # lack of a row to confirm that it didn't succeed
        form = create_xsd_and_populate("data/geopoint/geopoint_form.xhtml",
                                filename,
                                self.domain)
        cursor = connection.cursor()
        cursor.execute("SELECT count(*) FROM schema_geodomain_moz_sarahdemo_2")
        self.assertEqual(0, cursor.fetchone()[0] )
        
    
    def _check_row(self, lat=LAT, lon=LON, alt=ALT, acc=ACC):
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM schema_geodomain_moz_sarahdemo_2 order by id desc")
        row = cursor.fetchone()
        self.assertEqual(25, len(row))
        latback, lonback, altback, accback = row[20:24]
        
        self._checkValue(lat, latback)
        self._checkValue(lon, lonback)
        self._checkValue(alt, altback)
        self._checkValue(acc, accback)
        
    def _checkValue(self, expected, actual):
        if expected is None:
            self.assertEqual(expected, actual)
        else:
            self.assertAlmostEqual(expected, actual)