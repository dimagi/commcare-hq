# encoding: utf-8
from django.http.response import HttpResponse
from django.test import SimpleTestCase

from corehq.util.files import safe_filename, safe_filename_header


class TestSafeFilename(SimpleTestCase):

    def test_safe_for_fs_bytestring(self):
        self.assertEqual(safe_filename('spam*?: 𐍃𐍀𐌰𐌼-&.txt'), u'spam 𐍃𐍀𐌰𐌼-&.txt')

    def test_safe_for_fs_unicode(self):
        self.assertEqual(safe_filename(u'spam*?: 𐍃𐍀𐌰𐌼-&.txt'), u'spam 𐍃𐍀𐌰𐌼-&.txt')

    def test_basic_usage(self):
        filename = safe_filename('test', 'zip')
        self.assertEqual(filename, 'test.zip')

    def test_default_export_name(self):
        base_filename = "Surveys > Survey Category 1 (Ex. Household) > Survey 1: 2016-12-23 2016-12-23"
        # colons are not allowed in filenames on Mac
        # > and < are not allowed on Windows
        expected_name = u"Surveys  Survey Category 1 (Ex. Household)  Survey 1 2016-12-23 2016-12-23.zip"
        filename = safe_filename(base_filename, 'zip')
        self.assertEqual(filename, expected_name)

    def test_no_newlines(self):
        filename = safe_filename('line 1\nline 2', 'zip')
        self.assertEqual(filename, 'line 1line 2.zip')

    def test_newlines_and_wacky_unicode(self):
        base_filename = u"ICDS CAS - AWW > ड्य\n ूलिस्ट > टीकों का रà\n ��कार्ड: 2016-05-31 2016-05-31"
        expected_name = u"ICDS CAS - AWW  ड्य ूलिस्ट  टीकों का रà ��कार्ड 2016-05-31 2016-05-31.zip"
        filename = safe_filename(base_filename, 'zip')
        self.assertEqual(filename, expected_name)


class TestFormatFilename(SimpleTestCase):

    def assertWorksAsHeader(self, filename):
        # Django does some filename validation when trying to set this as a header
        response = HttpResponse()
        response['filename'] = filename


    # TODO generate cases with a series of these
