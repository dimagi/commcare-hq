# coding=utf-8
from lxml import etree
from django.test import SimpleTestCase
from corehq.apps.app_manager.translations import escape_output_value


class AppManagerTranslationsTest(SimpleTestCase):

    def test_escape_output_value(self):
        test_cases = [
            ('hello', '<value>hello</value>'),
            ('abc < def > abc', '<value>abc &lt; def &gt; abc</value>'),
            ("bee's knees", "<value>bee's knees</value>"),
            ('unfortunate <xml expression', '<value>unfortunate &lt;xml expression</value>'),
            (u'क्लिक', '<value>&#2325;&#2381;&#2354;&#2367;&#2325;</value>'),
            ('&#39', '<value>&amp;#39</value>'),
            ('Here is a ref <output value="/data/no_media" /> with some trailing text and bad < xml.',
             '<value>Here is a ref <output value="/data/no_media"/> with some trailing text and bad &lt; xml.</value>')

        ]
        for input, expected_output in test_cases:
            self.assertEqual(expected_output, etree.tostring(escape_output_value(input)))
