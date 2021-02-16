from django.test import SimpleTestCase
from ...templatetags.xforms_extras import \
    html_trans, html_trans_prefix, html_trans_prefix_delim, clean_trans


class TestHTMLTransFilter(SimpleTestCase):
    def test_primary_language_includes_no_tag(self):
        name_dict = {'en': 'English Output'}
        langs = ['en']
        result = html_trans(name_dict, langs)
        self.assertEqual(result, 'English Output')

    def test_non_primary_includes_appended_tag(self):
        name_dict = {'por': 'Portuguese Output'}
        langs = ['en', 'por']
        result = html_trans(name_dict, langs)
        unpadded_result = ' '.join(result.split())
        self.assertEqual(unpadded_result, 'Portuguese Output por')

    def test_no_language_returns_first_available_with_appended_tag(self):
        name_dict = {'en': 'English Output'}
        result = html_trans(name_dict)
        unpadded_result = ' '.join(result.split())
        self.assertEqual(unpadded_result, 'English Output en')


class TestHTMLTransPrefixFilter(SimpleTestCase):
    def test_primary_language_includes_no_tag(self):
        name_dict = {'en': 'English Output'}
        langs = ['en']
        result = html_trans_prefix(name_dict, langs)
        self.assertEqual(result, 'English Output')

    def test_non_primary_language_includes_prepended_html_tag(self):
        name_dict = {'por': 'Portuguese Output'}
        langs = ['en', 'por']
        result = html_trans_prefix(name_dict, langs)
        unpadded_result = ' '.join(result.split())
        self.assertEqual(unpadded_result,
            '<span class="btn btn-xs btn-info btn-langcode-preprocessed">por</span> Portuguese Output')

    def test_default_language_includes_prepended_html_tag(self):
        name_dict = {'en': 'English Output'}
        result = html_trans_prefix(name_dict)
        unpadded_result = ' '.join(result.split())
        self.assertEqual(unpadded_result,
            '<span class="btn btn-xs btn-info btn-langcode-preprocessed">en</span> English Output')


class TestHTMLTransPrefixDelimFilter(SimpleTestCase):
    def test_primary_language_includes_no_tag(self):
        name_dict = {'en': 'English Output'}
        langs = ['en']
        result = html_trans_prefix_delim(name_dict, langs)
        self.assertEqual(result, 'English Output')

    def test_non_primary_language_includes_prepended_tag(self):
        name_dict = {'por': 'Portuguese Output'}
        langs = ['en', 'por']
        result = html_trans_prefix_delim(name_dict, langs)
        self.assertEqual(result, ' [por] Portuguese Output')

    def test_default_language_includes_prepended_tag(self):
        name_dict = {'en': 'English Output'}
        result = html_trans_prefix_delim(name_dict)
        self.assertEqual(result, ' [en] English Output')


class TestCleanTransFilter(SimpleTestCase):
    def test_primary_language_includes_no_tag(self):
        name_dict = {'en': 'English Output'}
        langs = ['en']
        result = clean_trans(name_dict, langs)
        self.assertEqual(result, 'English Output')

    def test_non_primary_language_includes_no_tag(self):
        name_dict = {'por': 'Portuguese Output'}
        langs = ['en', 'por']
        result = clean_trans(name_dict, langs)
        self.assertEqual(result, 'Portuguese Output')

    def test_default_language_includes_no_tag(self):
        name_dict = {'en': 'English Output'}
        result = clean_trans(name_dict)
        self.assertEqual(result, 'English Output')
