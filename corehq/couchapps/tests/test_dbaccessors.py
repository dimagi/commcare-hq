from __future__ import absolute_import
from __future__ import unicode_literals

import uuid
from io import open

from django.core.files.uploadedfile import UploadedFile
from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.couchapps.dbaccessors import forms_have_multimedia
from corehq.form_processor.tests.utils import FormProcessorTestUtils

DOMAIN = 'test-attachments'
FORM_XML = """<?xml version='1.0' ?>
<data uiVersion="1" version="1" name="Form with attachment"
    xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns:cc="http://commcarehq.org/xforms"
    xmlns="{xmlns}">
    <attachment>fgg</attachment>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>321</n1:deviceID>
        <n1:timeStart>2015-04-08T12:00:01.000000Z</n1:timeStart>
        <n1:timeEnd>2015-04-08T12:05:01.000000Z</n1:timeEnd>
        <n1:username>demo</n1:username>
        <n1:userID>123</n1:userID>
        <n1:instanceID>{doc_id}</n1:instanceID>
    </n1:meta>
</data>
"""
APP_ID_1 = '123'
APP_ID_2 = '456'
XMLNS_1 = 'http://openrosa.org/formdesigner/abc'
XMLNS_2 = 'http://openrosa.org/formdesigner/def'
COMBOS = [
    (APP_ID_1, XMLNS_1, True),
    (APP_ID_2, XMLNS_2, True),
    (APP_ID_1, XMLNS_2, False),
    (APP_ID_2, XMLNS_1, False),
]


class AttachmentsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(AttachmentsTest, cls).setUpClass()
        for app_id, xmlns, with_attachments in COMBOS:
            AttachmentsTest._create_form(app_id, xmlns, with_attachments)

    @staticmethod
    def _create_form(app_id, xmlns, with_attachment):
        xml = FORM_XML.format(doc_id=uuid.uuid4().hex, xmlns=xmlns)
        attachments = {}
        if with_attachment:
            attachment = open('./corehq/ex-submodules/casexml/apps/case/tests/data/attachments/fruity.jpg', 'rb')
            attachments = {
                'pic.jpg': UploadedFile(attachment, 'pic.jpg')
            }
        submit_form_locally(xml, domain=DOMAIN, app_id=app_id, attachments=attachments)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        super(AttachmentsTest, cls).tearDownClass()

    def test_forms_have_multimedia(self):
        for app_id, xmlns, with_attachments in COMBOS:
            self.assertEqual(forms_have_multimedia(DOMAIN, app_id, xmlns), with_attachments, [app_id, xmlns])
