from datetime import datetime
from django.conf import settings
from django.test import TestCase
from django.contrib.auth.models import User
from couchdbkit import Server
from corehq.apps.users.signals import REGISTRATION_XMLNS

class UsersTestCase(TestCase):
        
    def testCreateBasicWebUser(self):
        """ 
        test that a basic couch user gets created properly after 
        saving a django user programmatically
        """
        username = "joe"
        email = "joe@domain.com"
        password = "password"
        # create django user
        new_user = User.objects.create_user(username, email, password)
        new_user.save()
        # the following will throw a HQUserProfile.DoesNotExist error
        # if the profile was not properly created
        profile = new_user.get_profile()
        # verify that the default couch stuff was created
        couch_user = profile.get_couch_user()
        self.assertEqual(couch_user.django_user.username, username)
        self.assertEqual(couch_user.django_user.email, email)

    def testCreateCompleteWebUser(self):
        """ 
        testing couch user internal functions
        """
        username = "joe"
        email = "joe@domain.com"
        password = "password"
        # create django user
        new_user = User.objects.create_user(username, email, password)
        new_user.save()
        # the following will throw a HQUserProfile.DoesNotExist error
        # if the profile was not properly created
        profile = new_user.get_profile()
        # verify that the default couch stuff was created
        couch_user = profile.get_couch_user()
        self.assertEqual(couch_user.django_user.username, username)
        self.assertEqual(couch_user.django_user.email, email)
        couch_user.add_domain_account('username1','domain1')
        self.assertEqual(couch_user.domain_accounts[0].username, 'username1')
        self.assertEqual(couch_user.domain_accounts[0].domain, 'domain1')
        couch_user.add_domain_account('username2','domain2')
        self.assertEqual(couch_user.domain_accounts[1].username, 'username2')
        self.assertEqual(couch_user.domain_accounts[1].domain, 'domain2')
        couch_user.add_commcare_account('username3','password3','domain3')
        self.assertEqual(couch_user.commcare_accounts[0].username, 'username3')
        self.assertEqual(couch_user.commcare_accounts[0].domain, 'domain3')
        couch_user.add_commcare_account('username4','password4','domain4')
        self.assertEqual(couch_user.commcare_accounts[1].username, 'username4')
        self.assertEqual(couch_user.commcare_accounts[1].domain, 'domain4')
        couch_user.add_phone_device('IMEI')
        self.assertEqual(couch_user.phone_devices[0].IMEI, 'IMEI')
        couch_user.add_phone_number('1234567890')
        self.assertEqual(couch_user.phone_numbers[0].number, '1234567890')
        couch_user.save()

    def testCreateUserFromRegistration(self):
        """ 
        test creating of couch user from a registration xmlns
        this is more of an integration test than a unit test,
        since 
        """
        sender = "post"
        from couchforms.models import XFormInstance
        from corehq.apps.users.models import CouchUser
        from corehq.apps.users.signals import create_user_from_commcare_registration
        xform = XFormInstance()
        xform.form = {}
        xform.form['username'] = username = 'test_registration'
        xform.form['password'] = password = '1982'
        xform.form['uuid'] = uuid = 'BXPKZLP49P3DDTJH3W0BRM2HV'
        xform.form['date'] = date_string = '2010-03-23'
        xform.form['registering_phone_id'] = registering_phone_id = '67QQ86GVH8CCDNSCL0VQVKF7A'
        xform.domain = domain = 'mockdomain'
        xform.xmlns = REGISTRATION_XMLNS
        doc_id = create_user_from_commcare_registration(sender, xform)
        couch_user = CouchUser.get(doc_id)
        # django_user = couch_user.get_django_user()
        # self.assertEqual(django_user.username, random_uuid)
        # self.assertEqual(couch_user.django_user.username, random_uuid)
        # registered commcare user gets an automatic domain account on server
        self.assertEqual(couch_user.domain_accounts[0].username, username)
        self.assertEqual(couch_user.domain_accounts[0].domain, domain)
        # they also get an automatic commcare account
        self.assertEqual(couch_user.commcare_accounts[0].username, username)
        self.assertEqual(couch_user.commcare_accounts[0].password, password)
        self.assertEqual(couch_user.commcare_accounts[0].domain, domain)
        self.assertEqual(couch_user.commcare_accounts[0].UUID, uuid)
        date = datetime.date(datetime.strptime(date_string,'%Y-%m-%d'))
        self.assertEqual(couch_user.commcare_accounts[0].date_registered, date)
        self.assertEqual(couch_user.phone_devices[0].IMEI, registering_phone_id)


