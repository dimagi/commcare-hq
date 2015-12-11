from django.core.files.uploadedfile import UploadedFile

from corehq.apps.receiverwrapper import submit_form_locally
from corehq.couchapps.dbaccessors import get_attachment_size_by_domain, get_attachment_size_by_domain_app_id_xmlns
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from django.test import TestCase
from dimagi.utils.make_uuid import random_hex

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
    (APP_ID_1, XMLNS_1, False),
    (APP_ID_1, XMLNS_2, False),
    (APP_ID_2, XMLNS_2, True),
]


class AttachmentsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        for app_id, xmlns, with_attachments in COMBOS:
            AttachmentsTest._create_form(app_id, xmlns, with_attachments)

    @staticmethod
    def _create_form(app_id, xmlns, with_attachment):
        xml = FORM_XML.format(doc_id=random_hex(), xmlns=xmlns)
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

    def test_get_attachment_size_by_domain(self):
        atts = get_attachment_size_by_domain(DOMAIN)
        self.assertIn((APP_ID_1, XMLNS_1), atts)
        self.assertIn((APP_ID_2, XMLNS_2), atts)
        self.assertNotIn((APP_ID_1, XMLNS_2), atts)
        self.assertNotIn((APP_ID_2, XMLNS_1), atts)

    def test_get_attachment_size_by_domain_app_id_xmlns_app_id(self):
        atts = get_attachment_size_by_domain_app_id_xmlns(DOMAIN, APP_ID_1)
        self.assertEqual(len(atts), 1)
        self.assertIn((APP_ID_1, XMLNS_1), atts)

    def test_get_attachment_size_by_domain_app_id_xmlns_xmlns_1(self):
        atts = get_attachment_size_by_domain_app_id_xmlns(DOMAIN, APP_ID_1, xmlns=XMLNS_1)
        self.assertEqual(len(atts), 1)
        self.assertIn((APP_ID_1, XMLNS_1), atts)

    def test_get_attachment_size_by_domain_app_id_xmlns_xmlns_2(self):
        atts = get_attachment_size_by_domain_app_id_xmlns(DOMAIN, APP_ID_1, xmlns=XMLNS_2)
        self.assertEqual(atts, {})
