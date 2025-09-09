from django.test import SimpleTestCase, RequestFactory
from corehq.util.test_utils import flag_enabled
from corehq.form_processor.utils.xform import sanitize_instance_xml


class TestSanitizeInstanceXML(SimpleTestCase):
    def test_does_nothing_with_feature_flags_off(self):
        initial_input = b'abc&#29;123'
        request = RequestFactory().get('/')
        self.assertEqual(sanitize_instance_xml(initial_input, request), initial_input)

    @flag_enabled('CONVERT_XML_GROUP_SEPARATOR')
    def test_replaces_group_separator_with_replacement_when_feature_flag_is_on(self):
        initial_input = b'abc&#29;123'
        request = RequestFactory().get('/')
        self.assertEqual(sanitize_instance_xml(initial_input, request), b'abc&#xFFFD;123')

    @flag_enabled('CONVERT_XML_GROUP_SEPARATOR')
    def test_replaces_all_occurrences(self):
        initial_input = b'abc&#29;123&#29;def'
        request = RequestFactory().get('/')
        self.assertEqual(sanitize_instance_xml(initial_input, request), b'abc&#xFFFD;123&#xFFFD;def')
