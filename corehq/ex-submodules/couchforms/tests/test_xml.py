#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

import uuid
import os
from couchforms.tests.testutils import post_xform_to_couch
from django.test import TestCase


class XMLElementTest(TestCase):

    def test_various_encodings(self):
        tests = (
            ('utf-8', u'हिन्दी चट्टानों'),
            ('UTF-8', u'हिन्दी चट्टानों'),
            ('ASCII', 'hello'),
        )
        file_path = os.path.join(os.path.dirname(__file__), "data", "encoding.xml")
        with open(file_path, "rb") as f:
            xml_template = f.read()

        for encoding, value in tests:
            xml_data = xml_template.format(
                encoding=encoding,
                form_id=uuid.uuid4().hex,
                sample_value=value.encode(encoding),
            )
            xform = post_xform_to_couch(xml_data)
            self.assertEqual(value, xform.form['test'])
            elem = xform.get_xml_element()
            self.assertEqual(value, elem.find('{http://commcarehq.org/couchforms-tests}test').text)
