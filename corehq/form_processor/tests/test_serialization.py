# -*- coding: utf-8 -*-
import uuid

from django.test import TestCase
from django.test.utils import override_settings

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import get_simple_form_xml


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class SerializationTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(SerializationTests, cls).setUpClass()
        cls.domain = uuid.uuid4().hex

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_xforms(cls.domain)
        super(SerializationTests, cls).tearDownClass()

    def test_serialize_attachments(self):
        form_id = uuid.uuid4().hex
        form_xml = get_simple_form_xml(form_id)
        form = submit_form_locally(form_xml, domain=self.domain)[1]

        form_xml = form.get_attachment_meta('form.xml')
        form_json = form.to_json(include_attachments=True)
        self.assertEqual(form_json['external_blobs']['form.xml']['id'], str(form_xml.attachment_id))
