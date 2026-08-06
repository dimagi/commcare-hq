import json

import pytest

from django.test import TestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.apps.translations.app_translations.ai_translator import (
    AppTranslationFormat,
    _string_key,
    is_valid_app_translation,
)
from corehq.apps.translations.const import MODE_FILL_MISSING, MODE_RETRANSLATE


@pytest.mark.parametrize("source, translated, valid", [
    ("Name", "Nom", True),
    ("Name", "", False),                      # empty output
    ("Name", None, False),                    # non-string output
    # <output> tags must survive verbatim (count + name sequence + attrs)
    ('Hello <output value="/data/name"/>', 'Bonjour <output value="/data/name"/>', True),
    ('Hello <output value="/data/name"/>', 'Bonjour', False),
    ('Hello <output value="/data/name"/>', 'Bonjour <output value="/data/nom"/>', False),
    # HTML tag sequence preserved
    ("<b>Save</b>", "<b>Enregistrer</b>", True),
    ("<b>Save</b>", "Enregistrer", False),
    # URLs preserved
    ("See https://example.com/help", "Voir https://example.com/help", True),
    ("See https://example.com/help", "Voir https://exemple.fr/aide", False),
    # %/{} have no runtime meaning in app content — free to change
    ("Hi {name}", "Salut {nom}", True),
    ("75% complete", "75 % terminé", True),
    # markdown renders on mobile: marker counts must survive
    ("**Warning** do not proceed", "**Attention** ne continuez pas", True),
    ("**Warning** do not proceed", "Attention ne continuez pas", False),
    # fill-in-the-blank runs may be resized but not dropped
    ("Name: ____", "Nom : ______", True),
    ("Name: ____", "Nom :", False),
    # list structure must keep the same number of items
    ("- Wash hands\n- Boil water", "- Lavez les mains\n- Faites bouillir l'eau", True),
    ("- Wash hands\n- Boil water", "Lavez les mains et faites bouillir l'eau", False),
    ("1. First\n2. Second", "1. Premier\n2. Deuxième", True),
    ("1. First\n2. Second", "Premier puis deuxième", False),
    # headings
    ("# Instructions", "# Instructions traduites", True),
    ("# Instructions", "Instructions traduites", False),
    # link syntax survives with the label translated
    ("See [help](https://example.com)", "Voir [aide](https://example.com)", True),
    ("See [help](https://example.com)", "Voir aide : https://example.com", False),
    # trailing punctuation swallowed by the URL regex must not fail it
    ("Go to (https://example.com/help)", "Aller à https://example.com/help !", True),
    # natural-language asterisks/hyphens that are not markdown never trip it
    ("Required *", "Requis", True),
    ("Follow-up visit", "Visite de suivi", True),
])
def test_is_valid_app_translation(source, translated, valid):
    assert is_valid_app_translation(source, translated) is valid


def _make_app():
    factory = AppFactory(build_version='2.40.0')
    factory.app.langs = ['en', 'fra']
    factory.new_basic_module('register', 'case')
    xform = XFormBuilder()
    xform.new_question('name', {'en': 'What is the name?', 'fra': ''})
    factory.app.get_module(0).get_form(0).source = xform.tostring().decode('utf-8')
    return factory.app


def test_load_input_fill_missing_extracts_untranslated_source_strings():
    app = _make_app()
    fmt = AppTranslationFormat(app, 'fra', mode=MODE_FILL_MISSING)
    units = fmt.load_input()
    # 2 names (Menus_and_forms), 2 case list/detail rows, 1 question label
    assert len(units) == 5
    sources = {u.source_text for u in units.values()}
    assert 'register module' in sources
    assert len({u.string_key for u in units.values()}) == len(units)  # keys unique


def test_string_keys_use_unique_ids_not_sheet_names():
    app = _make_app()
    fmt = AppTranslationFormat(app, 'fra', mode=MODE_RETRANSLATE)
    units = fmt.load_input()
    module_uid = app.get_module(0).unique_id
    form_uid = app.get_module(0).get_form(0).unique_id
    keys = {u.string_key for u in units.values()}
    assert any(k.startswith(f'["{module_uid}"') for k in keys)       # module sheet rows
    assert any(k.startswith(f'["{form_uid}"') for k in keys)         # form sheet rows
    assert any(k.startswith('["menus_and_forms"') for k in keys)     # top sheet rows
    assert not any('menu1' in k for k in keys)                       # nothing positional


def test_overlong_string_keys_compact_deterministically():
    long_identity = 'x' * 600  # e.g. an ID Mapping / graph-config row
    key = _string_key(('uid', long_identity, 1))
    assert len(key) <= 512  # fits AITranslation.string_key
    assert key == _string_key(('uid', long_identity, 1))          # stable
    assert key != _string_key(('uid', long_identity + 'y', 1))    # still unique


def test_string_keys_stable_when_modules_shift():
    """The same logical string keeps its key after another module is
    added and moved first — the failure mode positional keys corrupt."""
    app = _make_app()
    fmt = AppTranslationFormat(app, 'fra', mode=MODE_RETRANSLATE)
    keys_before = {u.source_text: u.string_key for u in fmt.load_input().values()}

    factory = AppFactory(build_version='2.40.0')
    factory.app = app
    factory.new_basic_module('aaa_first', 'case')
    app.rearrange_modules(len(app.modules) - 1, 0)

    fmt2 = AppTranslationFormat(app, 'fra', mode=MODE_RETRANSLATE)
    keys_after = {u.source_text: u.string_key for u in fmt2.load_input().values()}
    assert keys_after['register module'] == keys_before['register module']


def test_load_input_fill_missing_skips_already_translated():
    app = _make_app()
    app.get_module(0).name['fra'] = 'module inscription'
    fmt = AppTranslationFormat(app, 'fra', mode=MODE_FILL_MISSING)
    sources = {u.source_text for u in fmt.load_input().values()}
    assert 'register module' not in sources


def test_load_input_retranslate_includes_already_translated():
    app = _make_app()
    app.get_module(0).name['fra'] = 'module inscription'
    fmt = AppTranslationFormat(app, 'fra', mode=MODE_RETRANSLATE)
    sources = {u.source_text for u in fmt.load_input().values()}
    assert 'register module' in sources


def test_load_input_skips_manually_edited_keys():
    app = _make_app()
    fmt = AppTranslationFormat(app, 'fra', mode=MODE_RETRANSLATE)
    all_units = fmt.load_input()
    a_key = next(iter(all_units.values())).string_key
    fmt2 = AppTranslationFormat(
        app, 'fra', mode=MODE_RETRANSLATE, manually_edited_keys={a_key})
    assert len(fmt2.load_input()) == len(all_units) - 1


def test_create_batches_are_sheet_scoped_with_context_header():
    app = _make_app()
    fmt = AppTranslationFormat(app, 'fra')
    fmt.load_input()
    batches = fmt.create_batches(chunk_size=2)
    # 5 units over 3 sheets (Menus_and_forms: 2, module: 2, form: 1)
    assert [len(b) for b in batches] == [2, 2, 1]
    # a batch never mixes sheets
    for batch in batches:
        assert len({u.sheet_name for u in batch.values()}) == 1
    # first line is the context header naming the screen; rest is the payload
    header, _, body = fmt.format_input(batches[1]).partition('\n')
    assert 'register' in header
    payload = json.loads(body)
    assert all(isinstance(v, str) and v for v in payload.values())


def test_chunks_of_one_sheet_share_the_context_header():
    app = _make_app()
    fmt = AppTranslationFormat(app, 'fra')
    fmt.load_input()
    batches = fmt.create_batches(chunk_size=1)  # force chunking everywhere
    headers_by_sheet = {}
    for batch in batches:
        sheet = next(iter(batch.values())).sheet_name
        header = fmt.format_input(batch).partition('\n')[0]
        assert headers_by_sheet.setdefault(sheet, header) == header


def test_treat_default_copies_as_missing():
    app = _make_app()
    # source text copied into the target column — common in real apps
    app.get_module(0).name['fra'] = 'register module'
    fmt = AppTranslationFormat(app, 'fra')  # default: counts as translated
    assert 'register module' not in {u.source_text for u in fmt.load_input().values()}
    fmt2 = AppTranslationFormat(app, 'fra', treat_default_copies_as_missing=True)
    assert 'register module' in {u.source_text for u in fmt2.load_input().values()}


def test_parse_output_buffers_valid_and_skips_invalid():
    app = _make_app()
    fmt = AppTranslationFormat(app, 'fra')
    fmt.load_input()
    batches = fmt.create_batches(chunk_size=2)
    fmt.format_input(batches[0])  # marks batch 0 as the current batch
    uid = next(iter(batches[0]))
    parsed = fmt.parse_output(json.dumps({uid: 'traduction', 'bogus': 'x'}))
    assert parsed == {uid: 'traduction'}
    assert fmt.results == {uid: 'traduction'}
    assert fmt.parse_output('not json') == {}


class TestSaveOutput(TestCase):
    """save_output writes through the app document, which needs the test
    couch database."""

    def test_applies_buffered_translations_to_app(self):
        app = _make_app()
        fmt = AppTranslationFormat(app, 'fra')
        units = fmt.load_input()
        module_name_id = next(
            uid for uid, u in units.items() if u.source_text == 'register module')
        fmt.parse_output(json.dumps({module_name_id: 'module inscription'}))

        errors = fmt.save_output()

        assert errors == []
        assert app.get_module(0).name['fra'] == 'module inscription'
        assert app.get_module(0).name['en'] == 'register module'  # untouched
        assert fmt.applied_units() == {
            module_name_id: (units[module_name_id], 'module inscription')}

    def test_with_no_results_is_a_noop(self):
        app = _make_app()
        fmt = AppTranslationFormat(app, 'fra')
        fmt.load_input()
        assert fmt.save_output() == []

    def test_leaves_untranslated_rows_untouched(self):
        """Rows without buffered results are omitted from the sheet's row
        list; the updaters must not blank or alter their existing values —
        the same semantics as a partial user upload."""
        app = _make_app()
        app.get_module(0).name['fra'] = 'existing manual translation'
        fmt = AppTranslationFormat(app, 'fra', mode=MODE_RETRANSLATE)
        units = fmt.load_input()
        form_label_id = next(
            uid for uid, u in units.items() if u.source_text == 'What is the name?')
        fmt.parse_output(json.dumps({form_label_id: 'Quel est le nom ?'}))

        assert fmt.save_output() == []
        # the one translated string landed ...
        fmt2 = AppTranslationFormat(app, 'fra', mode=MODE_FILL_MISSING)
        remaining = {u.source_text for u in fmt2.load_input().values()}
        assert 'What is the name?' not in remaining
        # ... and the row we did NOT send kept its manual value
        assert app.get_module(0).name['fra'] == 'existing manual translation'
