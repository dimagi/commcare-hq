import unittest
import os
from datetime import date

from phone.models import Phone, PhoneUserInfo
from phone.processor import BACKUP_HANDLER, APP_NAME
from receiver.models import SubmissionHandlingOccurrence
from xformmanager.tests.util import populate

class RegistrationTestCase(unittest.TestCase):
    
    def setUp(self):
        Phone.objects.all().delete()
    
    def tearDown(self):
        Phone.objects.all().delete()
    
    def testBasicRegistration(self):
        
        path = os.path.dirname(__file__)
        data_path = os.path.join(path, "data")
        
        # Make sure there's nothing to start
        self.assertEqual(0, Phone.objects.count())
        
        # submit the xml
        populate("reg.xml", path=data_path)
        
        # should create a phone and user object
        self.assertEqual(1, Phone.objects.count())
        self.assertEqual(1, PhoneUserInfo.objects.count())
        
        # sanity check the data
        phone = Phone.objects.all()[0]
        user_info = PhoneUserInfo.objects.all()[0]
        self.assertEqual("67QQ86GVH8CCDNSCL0VQVKF7A", phone.device_id)
        self.assertEqual(phone, user_info.phone)
        self.assertEqual("phone_registered", user_info.status)
        self.assertEqual("test_registration", user_info.username)
        self.assertEqual("1982", user_info.password)
        self.assertEqual("BXPKZLP49P3DDTJH3W0BRM2HV", user_info.uuid)
        self.assertEqual(date(2010,03,23), user_info.registered_on)
        expected_data = {"sid":      "18",
                         "hcbpid":   "29",
                         "district": "district 9",
                         "region":   "ally",
                         "ward":     "collins"}
        additional_data = user_info.additional_data
        for key in expected_data:
            self.assertTrue(key in additional_data, 
                            "Key %s should be set in the additional data" % key)
            self.assertEqual(expected_data[key], additional_data[key],
                             "Value for %s was %s but should be %s" % \
                                (key, additional_data[key], expected_data[key]))
        
        for key in additional_data:
            self.assertTrue(key in expected_data,
                            "Extra key %s was found in submitted data" % key)
            