# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.form_processor.utils import get_simple_form_xml


@use_sql_backend
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
        submit_form_locally(form_xml, domain=self.domain)

        form = FormAccessorSQL().get_form(form_id)
        with self.assertNumQueries(1):
            # 1 query to fetch the form.xml attachment. The rest are lazy
            form_json = form.to_json(include_attachments=True)

        form_xml = form.get_attachment_meta('form.xml')

        with self.assertNumQueries(1):
            # lazy evaluation of attachments list
            self.assertEqual(form_json['external_blobs']['form.xml']['id'], str(form_xml.key))

        with self.assertNumQueries(1):
            # lazy evuation of history
            self.assertEqual(0, len(form_json['history']))
