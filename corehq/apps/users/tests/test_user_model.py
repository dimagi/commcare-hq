from django.test import TestCase

from corehq.apps.users.models import CommCareUser
from corehq.form_processor.utils import get_simple_wrapped_form, TestFormMetadata
from corehq.form_processor.tests.utils import run_with_all_backends, FormProcessorTestUtils


class UserModelTest(TestCase):

    def setUp(self):
        self.domain = 'my-domain'
        self.user = CommCareUser.create(
            domain=self.domain,
            username='birdman',
            password='***',
        )
        self.user.save()

        self.metadata = TestFormMetadata(
            domain=self.user.domain,
            user_id=self.user._id,
        )
        get_simple_wrapped_form('123', metadata=self.metadata)

    def tearDown(self):
        self.user.delete()
        FormProcessorTestUtils.delete_all_xforms(self.domain)

    @run_with_all_backends
    def test_get_forms(self):
        forms = list(self.user.get_forms())

        self.assertEqual(len(forms), 1)

    @run_with_all_backends
    def test_get_forms_no_wrap(self):
        form_ids = list(self.user.get_forms(wrap=False))

        self.assertEqual(len(form_ids), 1)
        self.assertEqual(form_ids[0], '123')

    def test_get_deleted_forms(self):
        form = get_simple_wrapped_form('deleted', metadata=self.metadata)
        form.doc_type = form.doc_type + '-Deleted'
        form.save()

        form_ids = list(self.user.get_forms(wrap=False))
        self.assertEqual(len(form_ids), 1)

        deleted_forms = list(self.user.get_forms(deleted=True))
        self.assertEqual(len(deleted_forms), 1)
        self.assertEqual(deleted_forms[0]['_id'], 'deleted')
