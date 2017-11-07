# encoding: utf-8
from __future__ import absolute_import
from django.http.response import HttpResponse
from django.test import SimpleTestCase

from corehq.util.files import safe_filename, safe_filename_header
from corehq.util.test_utils import generate_cases


class TestFormatFilename(SimpleTestCase):

    def assertWorksAsHeader(self, filename_header):
        # Django does some validation when trying to set this as a header
        response = HttpResponse()
        response['Content-Disposition'] = filename_header

    def test_add_extension(self):
        filename = safe_filename('test', 'zip')
        self.assertEqual(filename, 'test.zip')

    def test_header_format(self):
        header = safe_filename_header('test', 'zip')
        self.assertWorksAsHeader(header)
        expected = 'attachment; filename="test.zip"; filename*=UTF-8\'\'test.zip'
        self.assertEqual(header, expected)


@generate_cases([

    ('spam*?: 𐍃𐍀𐌰𐌼-&.txt',
     u'spam 𐍃𐍀𐌰𐌼-&.txt'),

    (u'spam*?: 𐍃𐍀𐌰𐌼-&.txt',
     u'spam 𐍃𐍀𐌰𐌼-&.txt'),

    ('line 1\nline 2',
     'line 1line 2'),

    # colons are not allowed in filenames on Mac, > and < are not allowed on Windows
    ("Surveys > Survey Category 1 (Ex. Household) > Survey 1: 2016-12-23 2016-12-23.zip",
     u"Surveys  Survey Category 1 (Ex. Household)  Survey 1 2016-12-23 2016-12-23.zip"),

    (u"ICDS CAS - AWW > ड्य\n ूलिस्ट > टीकों का रà\n ��कार्ड: 2016-05-31 2016-05-31.zip",
     u"ICDS CAS - AWW  ड्य ूलिस्ट  टीकों का रà ��कार्ड 2016-05-31 2016-05-31.zip"),

], TestFormatFilename)
def test_format_and_set_as_header(self, filename, expected_filename):
    self.assertEqual(safe_filename(filename), expected_filename)
    self.assertWorksAsHeader(safe_filename_header(filename))
