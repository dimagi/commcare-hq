import unittest
from datetime import date

from xformmanager.tests.util import clear_data, create_xsd_and_populate
from domain.models import Domain
from phone.models import Phone, PhoneUserInfo

class PhoneUserTestCase(unittest.TestCase):
    
    def setUp(self):
        # clean up, in case some other tests left some straggling
        # form data, we want to start with a clean test environment
        # each time.
        clear_data()
        Phone.objects.all().delete()
        PhoneUserInfo.objects.all().delete()
        self.domain = Domain.objects.get_or_create(name='phone_user_domain')[0]
        

    def testFormCreatesUserInfo(self):
        """
        Makes sure the creation of a form creates a new user_info object
        """
        self.assertEqual(0, Phone.objects.count())
        self.assertEqual(0, PhoneUserInfo.objects.count())
        create_xsd_and_populate("data/pf_new_reg.xsd", "data/pf_new_reg_1.xml", 
                                self.domain)
        
        # should create a phone and user object
        self.assertEqual(1, Phone.objects.count())
        self.assertEqual(1, PhoneUserInfo.objects.count())
        
        # sanity check the data
        phone = Phone.objects.all()[0]
        user_info = PhoneUserInfo.objects.all()[0]
        self.assertEqual("WK13O6ST8SWZVXLAI68B9YZWK", phone.device_id)
        self.assertEqual(phone, user_info.phone)
        self.assertEqual("lucy", user_info.username)
        self.assertEqual("auto_created", user_info.status)
        self.assertEqual(date.today(), user_info.registered_on)
        
        # None of these fields should be set
        self.assertEqual(None, user_info.user)
        self.assertEqual(None, user_info.password)
        self.assertEqual(None, user_info.uuid)
        self.assertEqual(None, user_info.additional_data)
