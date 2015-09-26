from django.test import TestCase
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from django_digest.test import Client


class DigestOtaRestoreTest(TestCase):
    """
    Integration test for django_digest based ota restore is tested
    """
    domain = "test"
    username = "testota"
    first_name = "ota"
    last_name = "restorer"
    password = "123"


    def setUp(self):
        create_domain(self.domain)
        self.couch_user = CommCareUser.create(self.domain, self.username, self.password)
        userID = self.couch_user.user_id
        self.couch_user.first_name = self.first_name
        self.couch_user.last_name = self.last_name
        self.couch_user.save()

    def tearDown(self):
        self.couch_user.delete()
        domain = Domain.get_by_name(self.domain)
        domain.delete()


    def testOtaRestore(self, password=None):
        client = Client()

        client.set_authorization(self.couch_user.username, password if password else self.password, method='Digest')

        resp = client.get('/a/%s/phone/restore' % self.domain, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.count("Successfully restored account %s!" % self.username) > 0)

    def testOtaRestorePasswordChange(self):
        self.testOtaRestore()
        new_password = '4567'

        # todo: this needs to likely call the coreqhq.apps.users..views.change_password view to keep it clean vs. this direct user manipulation
        django_user = self.couch_user.get_django_user()
        django_user.set_password(new_password)
        django_user.save()
        self.testOtaRestore(password=new_password)



