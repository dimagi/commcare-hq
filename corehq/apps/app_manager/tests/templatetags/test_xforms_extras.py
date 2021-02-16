from django.test import SimpleTestCase
from ...templatetags.xforms_extras import \
    html_trans, html_trans_prefix, html_trans_prefix_delim, clean_trans, trans, \
    html_name


class TestTransFilter(SimpleTestCase):
    def test_no_translations_returns_empty(self):
        empty_translation_dict = {}
        result = trans(empty_translation_dict)
        self.assertEqual(result, '')

    def test_unspecified_language_includes_tag(self):
        translation_dict = {'en': 'English Output'}
        result = trans(translation_dict)
        self.assertEqual(result, 'English Output [en] ')

    def test_exclude_language_only_outputs_translation(self):
        translation_dict = {'en': 'English Output'}
        result = trans(translation_dict, include_lang=False)
        self.assertEqual(result, 'English Output')

    def test_primary_language_excludes_tag(self):
        translation_dict = {'en': 'English Output'}
        langs = ['en']
        result = trans(translation_dict, langs=langs)
        self.assertEqual(result, 'English Output')

    def test_secondary_language_includes_tag(self):
        translation_dict = {'en': 'English Output'}
        langs = ['por', 'en']
        result = trans(translation_dict, langs=langs)
        self.assertEqual(result, 'English Output [en] ')

    def test_do_not_use_delimiter_includes_html_tag(self):
        translation_dict = {'en': 'English Output'}
        result = trans(translation_dict, use_delim=False)
        self.assertEqual(result,
            'English Output <span class="btn btn-xs btn-info btn-langcode-preprocessed">en</span> ')

    def test_prefix_puts_tag_in_front_of_translation(self):
        translation_dict = {'en': 'English Output'}
        result = trans(translation_dict, prefix=True)
        self.assertEqual(result, ' [en] English Output')

    def test_strip_tags_removes_tags_from_html_tag(self):
        translation_dict = {'en': 'English Output'}
        result = trans(translation_dict, use_delim=False, strip_tags=True)
        self.assertEqual(result, 'English Output en ')


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

    # NOTE: This test only documents existing behavior.
    # I think it's likely that stripping was only meant to remove the markup surrounding the language,
    # and that the user input should just be escaped
    def test_strips_tags(self):
        name_dict = {'en': '<b>Bold Tag</b>'}
        langs = ['en']
        result = html_trans(name_dict, langs)
        self.assertEqual(result, 'Bold Tag')

    def test_strips_tag_of_non_primary_language(self):
        name_dict = {'por': 'Portuguese Output'}
        langs = ['en', 'por']
        result = html_trans(name_dict, langs)
        self.assertEqual(result, 'Portuguese Output por ')

    # NOTE: More existing behavior. Given that it strips out other tags, this seems unintentional
    def test_empty_mapping_returns_empty_span(self):
        name_dict = {}
        langs = ['en', 'por']
        result = html_trans(name_dict, langs)
        self.assertEqual(result, '<span class="label label-info">Empty</span>')


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

    def test_empty_mapping_returns_empty_span(self):
        name_dict = {}
        langs = ['en', 'por']
        result = html_trans_prefix(name_dict, langs)
        self.assertEqual(result, '<span class="label label-info">Empty</span>')


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

    def test_empty_mapping_returns_empty_span(self):
        name_dict = {}
        langs = ['en', 'por']
        result = html_trans_prefix_delim(name_dict, langs)
        self.assertEqual(result, '<span class="label label-info">Empty</span>')


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


class TestHTMLNameFilter(SimpleTestCase):
    def test_strips_tags(self):
        result = html_name('<b>Name</b>')
        self.assertEqual(result, 'Name')

    # NOTE: Documenting existing behavior. This looks like a bug, given it strips tags otherwise
    def test_no_name_returns_empty_label(self):
        result = html_name('')
        self.assertEqual(result, '<span class="label label-info">Empty</span>')
