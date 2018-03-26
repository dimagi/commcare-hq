from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.apps.users.management.commands.gdpr_scrub_user import Command

from corehq.form_processor.tests.utils import (
    create_form_for_test
)
from six.moves import range

DOMAIN = 'test-form-accessor'
USER_ID = '123'


class GDPRScrubUserTests(TestCase):
    def setUp(self):
        super(GDPRScrubUserTests, self).setUp()
        self.db = TemporaryFilesystemBlobDB()

    def tearDown(self):
        self.db.close()
        super(GDPRScrubUserTests, self).tearDown()

    @use_sql_backend
    def test_replace_username_in_xml_for_sql(self):

        print("==========REACHED HEEER^^^^^^^^^^^^^^^^")

        forms = [create_form_for_test(DOMAIN) for i in range(1)]
        # new_username = "replacement_username"
        #
        # Command().replace_username_in_xml_for_sql(forms, new_username)

    #     form_ids = [form.form_id for form in forms]
    #     forms = FormAccessorSQL.get_forms(form_ids)
    #     self.assertEqual(3, len(forms))
    #
    #     other_form = create_form_for_test('other_domain')
    #     self.addCleanup(lambda: FormAccessorSQL.hard_delete_forms('other_domain', [other_form.form_id]))
    #
    #     attachments = list(FormAccessorSQL.get_attachments_for_forms(form_ids, ordered=True))
    #     self.assertEqual(3, len(attachments))
    #
    #     deleted = FormAccessorSQL.hard_delete_forms(DOMAIN, form_ids[1:] + [other_form.form_id])
    #     self.assertEqual(2, deleted)
    #
    #     forms = FormAccessorSQL.get_forms(form_ids)
    #     self.assertEqual(1, len(forms))
    #     self.assertEqual(form_ids[0], forms[0].form_id)
    #
    #     for attachment in attachments[1:]:
    #         with self.assertRaises(AttachmentNotFound):
    #             attachment.read_content()
    #
    #     self.assertIsNotNone(attachments[0].read_content())
    #     other_form = FormAccessorSQL.get_form(other_form.form_id)
    #     self.assertIsNotNone(other_form.get_xml())
    #
    # def test_replace_username_in_metadata_for_couch(self):
    #     forms = [create_form_for_test(DOMAIN) for i in range(3)]
    #     form_ids = [form.form_id for form in forms]
    #     forms = FormAccessorSQL.get_forms(form_ids)
    #     self.assertEqual(3, len(forms))
    #
    #     other_form = create_form_for_test('other_domain')
    #     self.addCleanup(lambda: FormAccessorSQL.hard_delete_forms('other_domain', [other_form.form_id]))
    #
    #     attachments = list(FormAccessorSQL.get_attachments_for_forms(form_ids, ordered=True))
    #     self.assertEqual(3, len(attachments))
    #
    #     deleted = FormAccessorSQL.hard_delete_forms(DOMAIN, form_ids[1:] + [other_form.form_id])
    #     self.assertEqual(2, deleted)
    #
    #     forms = FormAccessorSQL.get_forms(form_ids)
    #     self.assertEqual(1, len(forms))
    #     self.assertEqual(form_ids[0], forms[0].form_id)
    #
    #     for attachment in attachments[1:]:
    #         with self.assertRaises(AttachmentNotFound):
    #             attachment.read_content()
    #
    #     self.assertIsNotNone(attachments[0].read_content())
    #     other_form = FormAccessorSQL.get_form(other_form.form_id)
    #     self.assertIsNotNone(other_form.get_xml())
