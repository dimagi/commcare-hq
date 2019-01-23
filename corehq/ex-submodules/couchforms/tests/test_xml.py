# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
import os
from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.util.test_utils import TestFileMixin


class XMLElementTest(TestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_various_encodings(self):
        tests = (
            ('utf-8', 'हिन्दी चट्टानों'),
            ('UTF-8', 'हिन्दी चट्टानों'),
            ('ASCII', 'hello'),
        )
        xml_template = self.get_xml('encoding').decode('utf-8')

        for encoding, value in tests:
            xml_data = xml_template.format(
                encoding=encoding,
                form_id=uuid.uuid4().hex,
                sample_value=value,
            )
            xform = submit_form_locally(xml_data.encode('utf-8'), 'test-domain').xform
            self.assertEqual(value, xform.form_data['test'])
            elem = xform.get_xml_element()
            self.assertEqual(value, elem.find('{http://commcarehq.org/couchforms-tests}test').text)


@use_sql_backend
class XMLElementTestSQL(XMLElementTest):
    pass
