# encoding: utf-8
from django.http.response import HttpResponse
from django.test import SimpleTestCase

from corehq.apps.export.tasks import _format_filename
from corehq.util.files import safe_for_fs


class TestSafeFilename(SimpleTestCase):

    def test_safe_for_fs_bytestring(self):
        self.assertEqual(safe_for_fs('spam*?: 𐍃𐍀𐌰𐌼-&.txt'), 'spam 𐍃𐍀𐌰𐌼-&.txt')

    def test_safe_for_fs_unicode(self):
        self.assertEqual(safe_for_fs(u'spam*?: 𐍃𐍀𐌰𐌼-&.txt'), u'spam 𐍃𐍀𐌰𐌼-&.txt')


class TestFormatFilename(SimpleTestCase):

    def assertWorksAsHeader(self, filename):
        # Django does some filename validation when trying to set this as a header
        response = HttpResponse()
        response['filename'] = filename

    def test_basic_usage(self):
        filename = _format_filename('test', 'zip')
        self.assertEqual(filename, 'test.zip')
        self.assertWorksAsHeader(filename)

    def test_default_export_name(self):
        # This (with .zip) is a valid filename
        base_filename = "Surveys > Survey Category 1 (Ex. Household) > Survey 1: 2016-12-23 2016-12-23"
        filename = _format_filename(base_filename, 'zip')
        self.assertEqual(filename, base_filename + '.zip')
        self.assertWorksAsHeader(filename)

    def test_no_newlines(self):
        filename = _format_filename('line 1\nline 2', 'zip')
        self.assertEqual(filename, 'line 1line 2.zip')
        self.assertWorksAsHeader(filename)

    def test_newlines_and_wacky_unicode(self):
        base_filename = u"ICDS CAS - AWW > ड्य\n ूलिस्ट > टीकों का रà\n ��कार्ड: 2016-05-31 2016-05-31.zip"
        filename = _format_filename(base_filename, 'zip')
        self.assertWorksAsHeader(filename)
