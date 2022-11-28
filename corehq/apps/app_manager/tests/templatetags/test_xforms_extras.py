from django.utils.safestring import SafeString
from lxml.html import fragment_fromstring
from django.test import SimpleTestCase
from ...templatetags.xforms_extras import (
    html_trans,
    html_trans_prefix,
    clean_trans,
    trans,
    html_name,
    input_trans,
    inline_edit_trans
)


class TestTransFilter(SimpleTestCase):
    def test_no_translations_returns_empty(self):
        empty_translation_dict = {}
        result = trans(empty_translation_dict)
        self.assertEqual(result, '')

    def test_unspecified_language_includes_indicator(self):
        translation_dict = {'en': 'English Output'}
        result = trans(translation_dict)
        self.assertEqual(result, 'English Output [en] ')

    def test_primary_language_excludes_indicator(self):
        translation_dict = {'en': 'English Output'}
        langs = ['en']
        result = trans(translation_dict, langs=langs)
        self.assertEqual(result, 'English Output')

    def test_secondary_language_includes_indicator(self):
        translation_dict = {'en': 'English Output'}
        langs = ['por', 'en']
        result = trans(translation_dict, langs=langs)
        self.assertEqual(result, 'English Output [en] ')

    def test_does_not_escape_output_by_default(self):
        translation_dict = {'en': '<b>English Output</b>'}
        result = trans(translation_dict)
        self.assertEqual(result, '<b>English Output</b> [en] ')
        self.assertNotIsInstance(result, SafeString)


class TestHTMLTransFilter(SimpleTestCase):
    def test_primary_language_includes_no_indicator(self):
        name_dict = {'en': 'English Output'}
        langs = ['en']
        result = html_trans(name_dict, langs)
        self.assertEqual(result, 'English Output')

    def test_non_primary_includes_appended_indicator(self):
        name_dict = {'por': 'Portuguese Output'}
        langs = ['en', 'por']
        result = html_trans(name_dict, langs)
        unpadded_result = ' '.join(result.split())
        self.assertEqual(unpadded_result, 'Portuguese Output por')

    def test_no_language_returns_first_available_with_appended_indicator(self):
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

    def test_is_safe(self):
        name_dict = {'en': 'English Output'}
        langs = ['en']
        result = html_trans(name_dict, langs)
        self.assertIsInstance(result, SafeString)


class TestHTMLTransPrefixFilter(SimpleTestCase):
    def test_primary_language_includes_no_indicator(self):
        name_dict = {'en': 'English Output'}
        langs = ['en']
        result = html_trans_prefix(name_dict, langs)
        self.assertEqual(result, 'English Output')

    def test_non_primary_language_includes_prepended_html_indicator(self):
        name_dict = {'por': 'Portuguese Output'}
        langs = ['en', 'por']
        result = html_trans_prefix(name_dict, langs)
        unpadded_result = ' '.join(result.split())
        self.assertEqual(unpadded_result,
            '<span class="btn btn-xs btn-info btn-langcode-preprocessed">por</span> Portuguese Output')

    def test_default_language_includes_prepended_html_indicator(self):
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

    def test_is_safe(self):
        name_dict = {'en': 'English Output'}
        langs = ['en']
        result = html_trans_prefix(name_dict, langs)
        self.assertIsInstance(result, SafeString)


class TestCleanTransFilter(SimpleTestCase):
    def test_primary_language_includes_no_indicator(self):
        name_dict = {'en': 'English Output'}
        langs = ['en']
        result = clean_trans(name_dict, langs)
        self.assertEqual(result, 'English Output')

    def test_non_primary_language_includes_no_indicator(self):
        name_dict = {'por': 'Portuguese Output'}
        langs = ['en', 'por']
        result = clean_trans(name_dict, langs)
        self.assertEqual(result, 'Portuguese Output')

    def test_default_language_includes_no_indicator(self):
        name_dict = {'en': 'English Output'}
        result = clean_trans(name_dict)
        self.assertEqual(result, 'English Output')

    def test_does_not_escape_output(self):
        name_dict = {'en': '<b>English Output</b>'}
        result = clean_trans(name_dict)
        self.assertEqual(result, '<b>English Output</b>')
        self.assertNotIsInstance(result, SafeString)


class TestHTMLNameFilter(SimpleTestCase):
    def test_strips_tags(self):
        result = html_name('<b>Name</b>')
        self.assertEqual(result, 'Name')

    # NOTE: Documenting existing behavior. This looks like a bug, given it strips tags otherwise
    def test_no_name_returns_empty_label(self):
        result = html_name('')
        self.assertEqual(result, '<span class="label label-info">Empty</span>')


class TestInlineEditTransFilter(SimpleTestCase):
    @staticmethod
    def generate_markup_fragment(
        name_dict={'en': 'English Output'},
        langs=['en'],
        url='test-url',
        saveValueName='saveValue',
        postSave='postSave',
        containerClass='containerClass',
        iconClass='iconClass',
        readOnlyClass='readOnlyClass',
        disallow_edit='false'
    ):
        markup = inline_edit_trans(
            name_dict,
            langs,
            url,
            saveValueName,
            postSave,
            containerClass,
            iconClass,
            readOnlyClass,
            disallow_edit
        )

        return fragment_fromstring(markup)

    @classmethod
    def generate_params(cls, **kwargs):
        fragment = cls.generate_markup_fragment(**kwargs)
        return cls.dict_from_params(fragment.attrib['params'])

    @staticmethod
    def dict_from_params(params):
        unsplitPairs = params.split(',')
        pairs = [
            [token.strip() for token in pair.split(':')]
            for pair in unsplitPairs]
        pairs = [pair for pair in pairs if len(pair) == 2]
        return dict(pairs)

    def test_creates_inline_edit_tag(self):
        fragment = self.generate_markup_fragment()
        self.assertEqual(fragment.tag, 'inline-edit')

    def test_all_parameters(self):
        params = self.generate_params(
            name_dict={'en': 'English Output'},
            langs=['en'],
            url='test-url',
            saveValueName='saveValue',
            postSave='postSave',
            containerClass='containerClass',
            iconClass='iconClass',
            readOnlyClass='readOnlyClass',
            disallow_edit='false'
        )

        self.assertEqual(params['name'], "'name'")
        self.assertEqual(params['nodeName'], "'input'")
        self.assertEqual(params['url'], "'test-url'")
        self.assertEqual(params['saveValueName'], "'saveValue'")
        self.assertEqual(params['containerClass'], "'containerClass'")
        self.assertEqual(params['iconClass'], "'iconClass'")
        self.assertEqual(params['readOnlyClass'], "'readOnlyClass'")
        self.assertEqual(params['postSave'], 'postSave')
        self.assertEqual(params['disallow_edit'], 'false')

    def test_primary_language(self):
        params = self.generate_params(
            name_dict={'en': 'English Output'},
            langs=['en']
        )

        self.assertEqual(params['value'], "'English Output'")
        self.assertEqual(params['placeholder'], "'English Output'")
        self.assertEqual(params['lang'], "''")

    def test_secondary_language(self):
        params = self.generate_params(
            name_dict={'por': 'Portuguese Output'},
            langs=['en', 'por']
        )

        self.assertEqual(params['value'], "''")
        self.assertEqual(params['placeholder'], "'Portuguese Output'")
        self.assertEqual(params['lang'], "'por'")

    def test_no_available_translation(self):
        params = self.generate_params(
            name_dict={'en': 'English Output'},
            langs=[]
        )

        self.assertEqual(params['value'], "''")
        self.assertEqual(params['placeholder'], "'English Output'")
        self.assertEqual(params['lang'], "''")

    def test_uses_javascript_escaping_on_value_and_placeholder(self):
        params = self.generate_params(
            name_dict={'en': 'English; Output'},
            langs=['en']
        )

        self.assertEqual(params['value'], "'English\\u003B Output'")
        self.assertEqual(params['placeholder'], "'English\\u003B Output'")


class TestInputTransFilter(SimpleTestCase):
    @staticmethod
    def generate_markup_fragment(
        name_dict={'en': 'English Output'},
        langs=['en'],
        input_name='name',
        input_id='test_id',
        data_bind='data_binding',
        element_type='input_text'
    ):
        markup = input_trans(
            name=name_dict,
            langs=langs,
            input_name=input_name,
            input_id=input_id,
            data_bind=data_bind,
            element_type=element_type)

        return fragment_fromstring(markup)

    def test_creates_input_tag(self):
        fragment = self.generate_markup_fragment()
        self.assertEqual(fragment.tag, 'input')

    def test_creates_textarea_tag(self):
        fragment = self.generate_markup_fragment(element_type='textarea')
        self.assertEqual(fragment.tag, 'textarea')

    def test_fills_all_attributes(self):
        fragment = self.generate_markup_fragment(
            name_dict={'en': 'English Output'},
            langs=['en'],
            input_name='name',
            input_id='test_id',
            data_bind='data_binding'
        )

        self.assertEqual(fragment.attrib['type'], 'text')
        self.assertEqual(fragment.attrib['name'], 'name')
        self.assertEqual(fragment.attrib['id'], 'test_id')
        self.assertEqual(fragment.attrib['data-bind'], 'data_binding')
        self.assertEqual(fragment.attrib['class'], 'form-control')
        self.assertEqual(fragment.attrib['value'], 'English Output')
        self.assertEqual(fragment.attrib['placeholder'], '')

    def test_primary_language_populates_value(self):
        fragment = self.generate_markup_fragment(
            name_dict={'en': 'English Output'},
            langs=['en']
        )

        self.assertEqual(fragment.attrib['value'], 'English Output')
        self.assertEqual(fragment.attrib['placeholder'], '')

    def test_secondary_language_ignores_value_and_populates_placeholder(self):
        fragment = self.generate_markup_fragment(
            name_dict={'por': 'Portuguese Output'},
            langs=['en', 'por']
        )

        self.assertEqual(fragment.attrib['value'], '')
        self.assertEqual(fragment.attrib['placeholder'], 'Portuguese Output')

    def test_no_id_contains_no_id_attribute(self):
        fragment = self.generate_markup_fragment(input_name=None)

        self.assertFalse('input_id' in fragment.attrib)

    def test_no_data_binding_contains_no_data_binding(self):
        fragment = self.generate_markup_fragment(data_bind=None)

        self.assertFalse('data-bind' in fragment.attrib)

    # NOTE: documenting existing behavior -- I think this was a side effect
    # of the parsing logic also being used elsewhere, and I doubt 'value' is meant to have javascript-escaping
    def test_escapes_value_using_javascript_notation(self):
        fragment = self.generate_markup_fragment(
            name_dict={'en': 'English; Output'},
            langs=['en']
        )

        self.assertEqual(fragment.attrib['value'], 'English\\u003B Output')

    # NOTE: documenting existing behavior -- it is unlikely this needs to be javascript-escaped
    def test_escapes_placeholder_using_javascript_notation(self):
        fragment = self.generate_markup_fragment(
            name_dict={'por': 'Portuguese; Output'},
            langs=['en', 'por']
        )

        self.assertEqual(fragment.attrib['placeholder'], 'Portuguese\\u003B Output')
