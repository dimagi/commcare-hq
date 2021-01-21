from django.test import SimpleTestCase
from unittest.mock import MagicMock

from corehq.form_processor.models import Attachment


class AttachmentHasSizeTests(SimpleTestCase):
    def test_handles_no_size_property(self):
        raw_content = MagicMock(spec_set=[''])
        attachment = self.create_attachment_with_content(raw_content)
        self.assertFalse(attachment.has_size())

    def test_handles_None(self):
        raw_content = MagicMock(size=None, spec_set=['size'])
        attachment = self.create_attachment_with_content(raw_content)
        self.assertFalse(attachment.has_size())

    def test_handles_valid_size(self):
        raw_content = MagicMock(size=1024, spec_set=['size'])
        attachment = self.create_attachment_with_content(raw_content)
        self.assertTrue(attachment.has_size())

    @staticmethod
    def create_attachment_with_content(content):
        return Attachment(name='test_attachment', raw_content=content, content_type='text')
