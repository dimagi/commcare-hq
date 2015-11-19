#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

import uuid
import os
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from django.test import TestCase
from casexml.apps.case.tests.util import TEST_DOMAIN_NAME
from corehq.form_processor.test_utils import run_with_all_backends
from corehq.util.test_utils import TestFileMixin


class XMLElementTest(TestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    @run_with_all_backends
    def test_various_encodings(self):
        tests = (
            ('utf-8', u'हिन्दी चट्टानों'),
            ('UTF-8', u'हिन्दी चट्टानों'),
            ('ASCII', 'hello'),
        )
        xml_template = self.get_xml('encoding')

        for encoding, value in tests:
            xml_data = xml_template.format(
                encoding=encoding,
                form_id=uuid.uuid4().hex,
                sample_value=value.encode(encoding),
            )
            xform = FormProcessorInterface().post_xform(xml_data)
            self.assertEqual(value, xform.form_data['test'])
            elem = xform.get_xml_element()
            self.assertEqual(value, elem.find('{http://commcarehq.org/couchforms-tests}test').text)
