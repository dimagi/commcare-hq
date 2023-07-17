from django.test import TestCase

from nose.tools import assert_equal

from corehq.apps.domain.models import Domain
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, DomainMembership, WebUser

DOMAIN = 'fixture-test'


class OtaRestoreUserTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(OtaRestoreUserTest, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name(DOMAIN, is_active=True)
        cls.domain.commtrack_enabled = True
        cls.domain.save()
        cls.user = CommCareUser(domain=DOMAIN,
                                domain_membership=DomainMembership(domain=DOMAIN, location_id='1',
                                                                   assigned_location_ids=['1']))
        cls.restore_user = cls.user.to_ota_restore_user(DOMAIN)

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.domain.delete()
        super(OtaRestoreUserTest, cls).tearDownClass()

    def test_get_commtrack_location_id(self):
        self.assertEqual(self.restore_user.get_commtrack_location_id(), '1')


def test_user_types():
    for user, expected_type in [
            (WebUser(), 'web'),
            (CommCareUser(domain=DOMAIN), 'commcare'),
    ]:
        user_type = user.to_ota_restore_user(DOMAIN).user_session_data['commcare_user_type']
        yield assert_equal, user_type, expected_type
