from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict

from django.test import SimpleTestCase

from corehq.form_processor.utils.xform import build_form_xml_from_property_dict


class FormSubmissionBuilderTest(SimpleTestCase):

    def test_property_dict_to_xml_empty(self):
        self.assertEqual('', build_form_xml_from_property_dict({}))

    def test_property_dict_to_xml_single_item(self):
        self.assertEqual(
            '<my-property>some value</my-property>',
            build_form_xml_from_property_dict({'my-property': 'some value'})
        )

    def test_property_dict_to_xml_multiple_item(self):
        props = OrderedDict()
        props['p1'] = 'v1'
        props['p2'] = 'v2'
        self.assertEqual(
            '<p1>v1</p1><p2>v2</p2>',
            build_form_xml_from_property_dict(props)
        )

    def test_invalid_tag(self):
        with self.assertRaises(ValueError):
            build_form_xml_from_property_dict({'no spaces': 'are allowed'})
