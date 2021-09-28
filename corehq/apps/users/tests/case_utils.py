from django.test import TestCase

from corehq.apps.groups.models import Group
from corehq.apps.users.cases import get_wrapped_owner
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import user_id_to_username
from corehq.util.test_utils import generate_cases


class CaseUtilsTestCase(TestCase):

    def setUp(self):
        self.domain = 'test'

    def test_get_wrapped_user(self):
        user = CommCareUser.create(self.domain, 'wrapped-user-test', 'password', None, None)
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        wrapped = get_wrapped_owner(user._id)
        self.assertTrue(isinstance(wrapped, CommCareUser))

    def test_get_wrapped_group(self):
        group = Group(domain=self.domain, name='wrapped-group-test')
        group.save()
        self.addCleanup(group.delete)
        wrapped = get_wrapped_owner(group._id)
        self.assertTrue(isinstance(wrapped, Group))


@generate_cases(
    (
        (1, ),
        (1.0, ),
        (None, ),
        ('', ),
        ('foobar', ),
    ),
    CaseUtilsTestCase,
)
def test_invalid_ids(self, invalid_id):
    self.assertEqual(None, get_wrapped_owner(invalid_id))
    self.assertEqual(None, user_id_to_username(invalid_id))
