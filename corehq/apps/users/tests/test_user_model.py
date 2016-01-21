from django.test import TestCase

from corehq.apps.users.models import CommCareUser
from corehq.form_processor.utils import get_simple_wrapped_form, TestFormMetadata


class UserModelTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'my-domain'
        cls.user = CommCareUser.create(
            domain=cls.domain,
            username='birdman',
            password='***',
        )
        cls.user.save()

        metadata = TestFormMetadata(
            domain=cls.user.domain,
            user_id=cls.user._id,
        )
        get_simple_wrapped_form('123', metadata=metadata)

    def test_get_forms(self):
        forms = list(self.user.get_forms())

        self.assertEqual(len(forms), 1)

    def test_get_forms_no_wrap(self):
        form_ids = list(self.user.get_forms(wrap=False))

        self.assertEqual(len(form_ids), 1)
        self.assertEqual(form_ids[0], '123')
