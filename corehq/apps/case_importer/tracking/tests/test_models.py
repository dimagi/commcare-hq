from django.forms import modelform_factory
from django.test import SimpleTestCase

from corehq.apps.case_importer.tracking.models import CaseUploadRecord


class CaseUploadRecordFormTest(SimpleTestCase):

    def test_comment_is_optional(self):
        # comment is optional, so it must not block saving a record from the
        # Django admin
        form_class = modelform_factory(CaseUploadRecord, fields=['comment'])
        form = form_class(data={'comment': ''})
        self.assertTrue(form.is_valid(), form.errors)
