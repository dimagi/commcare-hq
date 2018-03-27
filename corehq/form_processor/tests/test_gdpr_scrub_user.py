from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.apps.users.management.commands.gdpr_scrub_user import Command
from corehq.form_processor.models import XFormAttachmentSQL
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.utils import get_simple_wrapped_form
import uuid

import xmltodict

DOMAIN = 'test-form-accessor'
GDPR_SIMPLE_FORM = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="{form_name}" xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns="{xmlns}">
    <dalmation_count>yes</dalmation_count>
    <n0:meta xmlns:n0="http://openrosa.org/jr/xforms">
        <n0:deviceID>{device_id}</n0:deviceID>
        <n0:timeStart>{time_start}</n0:timeStart>
        <n0:timeEnd>{time_end}</n0:timeEnd>
        <n0:username>{username}</n0:username>
        <n0:userID>{user_id}</n0:userID>
        <n0:instanceID>{uuid}</n0:instanceID>
        <n1:appVersion xmlns:n1="http://commcarehq.org/xforms"></n1:appVersion>
    </n0:meta>
    {case_block}
</data>"""


class GDPRScrubUserTests(TestCase):
    def setUp(self):
        super(GDPRScrubUserTests, self).setUp()
        self.db = TemporaryFilesystemBlobDB()
        self.new_username = "replacement_sql_username"

    def tearDown(self):
        self.db.close()
        super(GDPRScrubUserTests, self).tearDown()

    def test_parse_form_data(self):
        form = get_simple_wrapped_form(uuid.uuid4().hex, metadata=TestFormMetadata(domain=DOMAIN),
                                       simple_form=GDPR_SIMPLE_FORM)
        new_form_xml = Command().parse_form_data(form, self.new_username)
        new_form_dict = xmltodict.parse(new_form_xml)
        self.assertEqual(new_form_dict["data"]["n0:meta"]["n0:username"], self.new_username)

    @use_sql_backend
    def test_modify_attachment_xml_and_metadata_sql(self):
        form = get_simple_wrapped_form(uuid.uuid4().hex,
                                       metadata=TestFormMetadata(domain=DOMAIN),
                                       simple_form=GDPR_SIMPLE_FORM)
        new_form_xml = Command().parse_form_data(form, self.new_username)
        FormAccessors(DOMAIN).modify_attachment_xml_and_metadata(form, new_form_xml)

        # Test that the xml changed
        form_attachment_xml = form.get_attachment("form.xml")
        form_attachment_dict = xmltodict.parse(form_attachment_xml)
        username_in_dict = form_attachment_dict["data"]["n0:meta"]["n0:username"]

        self.assertEqual(username_in_dict, self.new_username)

        # Test that the metadata changed in the database
        attachment_metadata = form.get_attachment_meta("form.xml")
        form_data_from_db = XFormAttachmentSQL.read_content(attachment_metadata)
        attachment_metadata_dict = xmltodict.parse(form_data_from_db)
        self.assertEqual(attachment_metadata_dict["data"]["n0:meta"]["n0:username"], self.new_username)

        # Test the operations
        operations = FormAccessors(DOMAIN).db_accessor.get_form_operations(form.form_id)
        print("OPERATIONS: {}".format(operations))

    def test_modify_attachment_xml_and_metadata_couch(self):
        form = get_simple_wrapped_form(uuid.uuid4().hex,
                                       metadata=TestFormMetadata(domain=DOMAIN),
                                       simple_form=GDPR_SIMPLE_FORM)
        new_form_xml = Command().parse_form_data(form, self.new_username)
        FormAccessors(DOMAIN).modify_attachment_xml_and_metadata(form, new_form_xml)

        # Test that the metadata changed in the database
        form_attachment_xml = form.get_attachment("form.xml")
        form_attachment_dict = xmltodict.parse(form_attachment_xml)
        username_in_dict = form_attachment_dict["data"]["n0:meta"]["n0:username"]

        self.assertEqual(username_in_dict, self.new_username)
