import os
import json
import unittest
from datetime import date

from corehq.apps.domain.models import Domain
from corehq.apps.phone.models import Phone, PhoneUserInfo
from corehq.apps.phone.processor import APP_NAME, REGISTRATION_HANDLER
from corehq.apps.receiver.models import SubmissionHandlingOccurrence
from corehq.apps.xforms.tests.util import populate

class RegistrationTestCase(unittest.TestCase):
    
    def setUp(self):
        Phone.objects.all().delete()
        self.domain = Domain.objects.get_or_create(name='reg_domain')[0]
        self.domain.is_active = True
        self.domain.save()

    
    def tearDown(self):
        Phone.objects.all().delete()
    
    def testBasicRegistration(self):
        
        path = os.path.dirname(__file__)
        data_path = os.path.join(path, "data")
        
        # Make sure there's nothing to start
        self.assertEqual(0, Phone.objects.count())
        
        # submit the xml
        submission = populate("reg.xml", domain=self.domain, path=data_path)
        
        # should create a phone and user object
        self.assertEqual(1, Phone.objects.count())
        self.assertEqual(1, PhoneUserInfo.objects.count())
        
        # sanity check the data
        phone = Phone.objects.all()[0]
        user_info = PhoneUserInfo.objects.all()[0]
        django_user = user_info.user
        
        # phone
        self.assertEqual("67QQ86GVH8CCDNSCL0VQVKF7A", phone.device_id)
        
        # phone user info
        self.assertEqual(phone, user_info.phone)
        self.assertEqual(submission.attachments.all()[0], user_info.attachment)
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
        additional_data = json.loads(user_info.additional_data)
        for key in expected_data:
            self.assertTrue(key in additional_data, 
                            "Key %s should be set in the additional data" % key)
            self.assertEqual(expected_data[key], additional_data[key],
                             "Value for %s was %s but should be %s" % \
                                (key, additional_data[key], expected_data[key]))
        
        for key in additional_data:
            self.assertTrue(key in expected_data,
                            "Extra key %s was found in submitted data" % key)
            
        # django user 
        self.assertNotEqual(None, django_user)
        self.assertEqual("test_registration", django_user.username)
        user_domains = Domain.active_for_user(django_user)
        self.assertEqual(1, user_domains.count())
        self.assertEqual(self.domain, user_domains.all()[0])
        
        # also, make sure we created an instance of the right handler
        way_handled = SubmissionHandlingOccurrence.objects.get\
                            (submission=user_info.attachment.submission)
        self.assertEqual(APP_NAME, way_handled.handled.app)
        self.assertEqual(REGISTRATION_HANDLER, way_handled.handled.method)    