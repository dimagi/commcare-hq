from uuid import uuid4

from django.test import TestCase

from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.apps.case_importer.tracking.views import _get_case_upload_record
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser


class GetCaseUploadRecordTest(TestCase):
    """``_get_case_upload_record`` backs every per-upload endpoint (file
    download, status, form/case IDs, comment), each of which turns
    ``DoesNotExist`` into a 404."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain('test-case-importer-hide-views')
        cls.domain = cls.domain_obj.name
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(cls.domain, 'hide-views-user', 'password', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain, deleted_by=None)

    def _make_upload(self, is_hidden):
        upload = CaseUploadRecord(
            upload_id=uuid4(),
            task_id=uuid4(),
            domain=self.domain,
            is_hidden=is_hidden,
        )
        upload.save()
        self.addCleanup(upload.delete)
        return upload

    def test_returns_visible_record(self):
        visible = self._make_upload(is_hidden=False)
        self.assertEqual(
            _get_case_upload_record(self.domain, visible.upload_id, self.user).pk,
            visible.pk,
        )

    def test_hidden_record_is_not_found(self):
        hidden = self._make_upload(is_hidden=True)
        with self.assertRaises(CaseUploadRecord.DoesNotExist):
            _get_case_upload_record(self.domain, hidden.upload_id, self.user)
