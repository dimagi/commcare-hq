from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.apps.users.management.commands.gdpr_scrub_user_from_forms import Command
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.utils import get_simple_wrapped_form

import uuid

DOMAIN = 'test-form-accessor'

GDPR_SIMPLE_FORM = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="{form_name}" xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns="{xmlns}">
    {form_properties}
    <n0:meta xmlns:n0="http://openrosa.org/jr/xforms">
        <n0:deviceID>{device_id}</n0:deviceID>
        <n0:timeStart>{time_start}</n0:timeStart>
        <n0:timeEnd>{time_end}</n0:timeEnd>
        <n0:username>{username}</n0:username>
        <n0:userID>{user_id}</n0:userID>
        <n1:appVersion xmlns:n1="http://commcarehq.org/xforms"></n1:appVersion>
    </n0:meta>
    {case_block}
</data>"""

EXPECTED_FORM_XML = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="New Form" xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns="http://openrosa.org/formdesigner/form-processor">
    <n0:meta xmlns:n0="http://openrosa.org/jr/xforms">
        <n0:deviceID>DEV IL</n0:deviceID>
        <n0:timeStart>2013-04-19T16:53:02.000000Z</n0:timeStart>
        <n0:timeEnd>2013-04-19T16:52:02.000000Z</n0:timeEnd>
        <n0:username>replacement_username</n0:username>
        <n0:userID>cruella_deville</n0:userID>
        <n1:appVersion xmlns:n1="http://commcarehq.org/xforms"></n1:appVersion>
    </n0:meta>
</data>"""

NEW_USERNAME = "replacement_username"


class UpdateFormTests(TestCase):

    def test_update_form_data(self):
        form = get_simple_wrapped_form(uuid.uuid4().hex,
                                       metadata=TestFormMetadata(domain=DOMAIN),
                                       simple_form=GDPR_SIMPLE_FORM)
        actual_form_xml = Command().update_form_data(form, NEW_USERNAME).decode('utf-8')
        self.assertXMLEqual(EXPECTED_FORM_XML, actual_form_xml)


class GDPRScrubUserFromFormsCouchTests(TestCase):
    def setUp(self):
        super(GDPRScrubUserFromFormsCouchTests, self).setUp()
        self.db = TemporaryFilesystemBlobDB()

    def tearDown(self):
        self.db.close()
        super(GDPRScrubUserFromFormsCouchTests, self).tearDown()

    def test_modify_attachment_xml_and_metadata_couch(self):
        form = get_simple_wrapped_form(uuid.uuid4().hex,
                                       metadata=TestFormMetadata(domain=DOMAIN),
                                       simple_form=GDPR_SIMPLE_FORM)
        new_form_xml = Command().update_form_data(form, NEW_USERNAME)
        FormAccessors(DOMAIN).modify_attachment_xml_and_metadata(form, new_form_xml, NEW_USERNAME)

        # Test that the metadata changed in the database
        actual_form_xml = form.get_attachment("form.xml").decode('utf-8')
        self.assertXMLEqual(EXPECTED_FORM_XML, actual_form_xml)

        # Test that the operations history is updated in this form
        refetched_form = FormAccessors(DOMAIN).get_form(form.form_id)
        self.assertEqual(len(refetched_form.history), 1)
        self.assertEqual(refetched_form.history[0].operation, "gdpr_scrub")
        self.assertEqual(refetched_form.metadata.username, NEW_USERNAME)


@use_sql_backend
class GDPRScrubUserFromFormsSqlTests(GDPRScrubUserFromFormsCouchTests):
    pass
