from django.test import TestCase

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase

from .utils import create_case


class UsercaseAccessorsTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(UsercaseAccessorsTests, cls).setUpClass()
        cls.domain = Domain(name='foo')
        cls.domain.save()
        cls.addClassCleanup(cls.domain.delete)
        cls.user = CommCareUser.create(cls.domain.name, 'username', 's3cr3t', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain.name, deleted_by=None)

    def setUp(self):
        create_case(
            self.domain.name,
            case_type=USERCASE_TYPE,
            user_id=self.user._id,
            name="bar",
            external_id=self.user._id,
            save=True,
        )

    def test_get_usercase(self):
        usercase = CommCareCase.objects.get_case_by_external_id(
            self.domain.name, self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(usercase)
        self.assertEqual(usercase.name, 'bar')
