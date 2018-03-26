from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.utils import get_simple_form_xml, convert_xform_to_json
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.apps.users.management.commands.gdpr_scrub_user import Command
from corehq.form_processor.models import XFormAttachmentSQL
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.utils import get_simple_wrapped_form
import uuid

from corehq.form_processor.tests.utils import (
    create_form_for_test
)
from corehq.form_processor.models import Attachment
import xmltodict

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
        # Create a form
        form = create_form_for_test(DOMAIN)
        new_username = "replacement_username"
        Command().replace_username_in_xml_for_sql(form, new_username)

        # Test that the xml changed
        form_attachment_xml = form.get_attachment("form.xml")
        form_attachment_dict = xmltodict.parse(form_attachment_xml)
        username_in_dict = form_attachment_dict["data"]["n0:meta"]["n0:username"]

        self.assertEqual(username_in_dict, new_username)

        # Test that the database updated
        attachment_metadata = form.get_attachment_meta("form.xml")
        # Read content:
        form_data_from_db = XFormAttachmentSQL.read_content(attachment_metadata)
        attachment_metadata_dict = xmltodict.parse(form_data_from_db)
        self.assertEqual(attachment_metadata_dict["data"]["n0:meta"]["n0:username"], new_username)

    def test_replace_username_in_metadata_for_couch(self):




        # # Create an attachment
        # form_id = 123
        # test_metadata = TestFormMetadata(
        #     domain=DOMAIN,
        #     username="orig_username"
        #     # time_end=datetime.utcnow(),
        #     # received_on=datetime.utcnow(),
        # )
        # # form_xml = get_simple_form_xml(form_id=form_id, metadata=test_metadata)
        # # print("form xml: {}".format(form_xml))
        # # Attachment(name='form.xml', raw_content=form_xml, content_type='text/xml')
        #
        # form = create_form_for_test(DOMAIN, attachments=test_metadata)
        new_username = "replacement_couch_username"

        form = get_simple_wrapped_form(uuid.uuid4().hex, metadata=TestFormMetadata(domain=DOMAIN))

        Command().replace_username_in_metadata_for_couch(form, new_username)
