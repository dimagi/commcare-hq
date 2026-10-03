import json
from collections import defaultdict
from unittest.mock import patch

from django.forms.models import model_to_dict
from django.test import TestCase

import pytest
from unmagic import use

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.apps.translations.app_translations import ai_translator
from corehq.apps.translations.app_translations.ai_translator import (
    AppTranslationFormat,
    ChangedAITranslations,
    _apply_translations,
    _rebase_results,
    _record_run,
    _refresh_provenance_statuses,
    _saved_units,
    _string_key,
    find_changed_ai_translations,
    is_valid_app_translation,
    prepare_translation_format,
    run_app_translation,
)
from corehq.apps.translations.const import MODE_FILL_MISSING, MODE_RETRANSLATE
from corehq.apps.translations.exceptions import AppChangedDuringTranslation
from corehq.apps.translations.models import AITranslation, AITranslationUsage


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
    # punctuation right after a URL is not part of it and must not fail it
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


# Keys for the six strings that _make_app() produces.
MODULE_NAME_KEY = '["menus_and_forms","register_module","Menu"]'  # 'register module'
FORM_NAME_KEY = '["menus_and_forms","register_form_0","Form"]'  # 'register form 0'
CASE_LIST_KEY = '["register_module","name","list",1]'  # 'Name'
CASE_DETAIL_KEY = '["register_module","name","detail",1]'  # 'Name'
QUESTION_KEY = '["register_form_0","name-label",1]'  # 'What is the name?'
SUBMIT_LABEL_KEY = '["register_form_0","submit_label",1]'  # 'Submit'
ALL_STRING_KEYS = {
    MODULE_NAME_KEY, FORM_NAME_KEY, CASE_LIST_KEY, CASE_DETAIL_KEY,
    QUESTION_KEY, SUBMIT_LABEL_KEY,
}


def test_load_input_fill_missing_extracts_untranslated_source_strings():
    app = _make_app()
    fmt = AppTranslationFormat(app, 'fra', mode=MODE_FILL_MISSING)
    units = fmt.load_input()
    # the submit label already has its 'Submit' default
    assert sorted(u.string_key for u in units.values()) == sorted(
        ALL_STRING_KEYS - {SUBMIT_LABEL_KEY})


def test_all_app_strings_includes_strings_load_input_skips():
    app = _make_app()
    app.get_module(0).name['fra'] = 'mon module'  # for MODULE_NAME_KEY
    fmt = AppTranslationFormat(app, 'fra', manually_edited_keys={QUESTION_KEY})

    all_strings = fmt.all_app_strings()
    units = fmt.load_input()

    assert all_strings.keys() == ALL_STRING_KEYS
    # load_input skips the translated module name and submit label, and
    # the edited question
    unit_keys = {u.string_key for u in units.values()}
    assert unit_keys == {FORM_NAME_KEY, CASE_LIST_KEY, CASE_DETAIL_KEY}
    assert all_strings[MODULE_NAME_KEY].target_text == 'mon module'
    assert all_strings[SUBMIT_LABEL_KEY].target_text == 'Submit'


def test_all_app_strings_leaves_out_strings_without_source():
    app = _make_app()
    xform = XFormBuilder()
    xform.new_question('name', {'en': '', 'fra': 'Quel nom ?'})
    app.get_module(0).get_form(0).source = xform.tostring().decode('utf-8')

    all_strings = AppTranslationFormat(app, 'fra').all_app_strings()

    assert all_strings.keys() == ALL_STRING_KEYS - {QUESTION_KEY}


def _record_ai_translation(app, string_key, source, translated, lang='fra'):
    return AITranslation.objects.create(
        domain=app.domain, app_id=app.get_id, lang=lang, string_key=string_key,
        source_value=source, translated_value=translated)


AI_SOURCE = 'register module'
AI_TRANSLATION = 'module inscription'
UNCHANGED = ChangedAITranslations(manually_edited=set(), stale=set())
EDITED = ChangedAITranslations(manually_edited={MODULE_NAME_KEY}, stale=set())
STALE = ChangedAITranslations(manually_edited=set(), stale={MODULE_NAME_KEY})


@pytest.mark.parametrize("app_source, app_translation, expected", [
    pytest.param(AI_SOURCE, AI_TRANSLATION, UNCHANGED, id='unchanged'),
    pytest.param(AI_SOURCE, 'module enregistrement', EDITED, id='edited'),
    # missing again, so fill_missing translates it like any other
    pytest.param(AI_SOURCE, '', UNCHANGED, id='cleared'),
    pytest.param('enrol module', AI_TRANSLATION, STALE, id='source-changed'),
    # the edit wins
    pytest.param('enrol module', 'module enregistrement', EDITED, id='both-changed'),
])
@use('db')
def test_find_changed_ai_translations(app_source, app_translation, expected):
    app = _make_app()
    app._id = 'test-app-id'
    _record_ai_translation(app, MODULE_NAME_KEY, AI_SOURCE, AI_TRANSLATION)
    app.get_module(0).name.update({'en': app_source, 'fra': app_translation})

    assert find_changed_ai_translations(AppTranslationFormat(app, 'fra')) == expected


@use('db')
def test_find_changed_ai_translations_ignores_strings_gone_from_app():
    app = _make_app()
    app._id = 'test-app-id'
    _record_ai_translation(
        app, '["deleted_module","name",1]', AI_SOURCE, AI_TRANSLATION)

    assert find_changed_ai_translations(AppTranslationFormat(app, 'fra')) == UNCHANGED


@use('db')
def test_find_changed_ai_translations_ignores_other_languages():
    app = _make_app()
    app._id = 'test-app-id'
    app.langs = ['en', 'fra', 'hin']
    _record_ai_translation(
        app, MODULE_NAME_KEY, AI_SOURCE, AI_TRANSLATION, lang='hin')
    app.get_module(0).name['fra'] = 'module enregistrement'

    assert find_changed_ai_translations(AppTranslationFormat(app, 'fra')) == UNCHANGED


def test_saved_units_keeps_result_the_ai_returned_unchanged():
    app = _make_app()
    # French translation present for the app
    app.get_module(0).name['fra'] = 'ancien'
    fmt = AppTranslationFormat(app, 'fra', mode=MODE_RETRANSLATE)
    [uid] = [uid for uid, u in fmt.load_input().items() if u.string_key == MODULE_NAME_KEY]
    # AI results also returned the same translation
    fmt.results = {uid: 'ancien'}
    saved_units = _saved_units(fmt, fmt.for_app(app).all_app_strings())

    # No other strings were translated only the one we sent, and it was unchanged
    assert [u.target_text for u in saved_units] == ['ancien']


@use('db')
def test_refresh_provenance_statuses():
    app = _make_app()
    app._id = 'test-app-id'

    form = app.get_module(0).get_form(0)

    # Translation already present in the app
    app.get_module(0).name['fra'] = AI_TRANSLATION
    form.name['fra'] = 'formulaire modifié'

    unchanged = _record_ai_translation(app, MODULE_NAME_KEY, AI_SOURCE, AI_TRANSLATION)
    edited = _record_ai_translation(app, FORM_NAME_KEY, form.name['en'], 'formulaire')
    removed = _record_ai_translation(app, '["deleted_module","name",1]', 'old', 'ancien')
    fmt = AppTranslationFormat(app, 'fra')

    assert _refresh_provenance_statuses(fmt, fmt.all_app_strings()) == 1
    assert dict(AITranslation.objects.filter(app_id=app.get_id).values_list('id', 'status')) == {
        unchanged.id: AITranslation.STATUS_APPLIED,
        edited.id: AITranslation.STATUS_MANUALLY_EDITED,
        removed.id: AITranslation.STATUS_REMOVED,
    }
    assert AITranslation.objects.get(id=unchanged.id).updated_on == unchanged.updated_on


@use('db')
def test_prepare_translation_format_finds_edited_and_stale_strings():
    app = _make_app()
    app._id = 'test-app-id'
    form = app.get_module(0).get_form(0)
    _record_ai_translation(app, MODULE_NAME_KEY, AI_SOURCE, AI_TRANSLATION)
    _record_ai_translation(app, FORM_NAME_KEY, form.name['en'], 'formulaire')
    app.get_module(0).name['fra'] = 'mon module'  # a user edited the AI translation
    form.name.update({'en': 'enrol form', 'fra': 'formulaire'})  # its source changed

    fmt = prepare_translation_format(app, 'fra', MODE_FILL_MISSING)

    assert fmt.manually_edited_keys == {MODULE_NAME_KEY}
    assert fmt.stale_keys == {FORM_NAME_KEY}


@use('db')
def test_prepare_translation_format_finds_ai_translated_strings():
    app = _make_app()
    app._id = 'test-app-id'
    _record_ai_translation(app, MODULE_NAME_KEY, AI_SOURCE, AI_TRANSLATION)

    fmt = prepare_translation_format(
        app, 'fra', MODE_FILL_MISSING, treat_default_copies_as_missing=True)

    assert fmt.ai_translated_keys == {MODULE_NAME_KEY}


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
    units = fmt2.load_input()
    assert a_key not in {u.string_key for u in units.values()}
    assert len(units) == len(all_units) - 1


def test_load_input_extracts_stale_keys():
    app = _make_app()
    app.get_module(0).name['fra'] = 'module inscription'
    fmt = AppTranslationFormat(app, 'fra', stale_keys={MODULE_NAME_KEY})

    unit_keys = {u.string_key for u in fmt.load_input().values()}

    assert MODULE_NAME_KEY in unit_keys


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


def test_chunks_within_each_sheet_share_the_context_header():
    app = _make_app()
    fmt = AppTranslationFormat(app, 'fra')
    units = fmt.load_input()
    batches = fmt.create_batches(chunk_size=1)  # force chunking everywhere
    assert len(batches) == len(units)  # one batch per unit
    headers_by_sheet = defaultdict(set)
    for batch in batches:
        sheet = next(iter(batch.values())).sheet_name
        headers_by_sheet[sheet].add(fmt.format_input(batch).partition('\n')[0])
    assert len(headers_by_sheet) == 3  # Menus_and_forms + module + form
    for headers in headers_by_sheet.values():
        assert len(headers) == 1


def test_treat_default_copies_as_missing():
    """A "default copy" is a target-language cell holding a verbatim
    copy of the default-language text, so it looks translated but isn't.
    Sheet generation manufactures these for form sheets: untranslated
    question labels fall back to the first non-empty language's text
    (download.get_form_question_label_name_media), and re-uploading a
    downloaded sheet persists the copies into the app."""
    app = _make_app()
    app.get_module(0).name['fra'] = 'register module'
    fmt = AppTranslationFormat(app, 'fra')  # default: counts as translated
    assert 'register module' not in {u.source_text for u in fmt.load_input().values()}
    fmt2 = AppTranslationFormat(app, 'fra', treat_default_copies_as_missing=True)
    assert 'register module' in {u.source_text for u in fmt2.load_input().values()}


def test_default_copies_the_ai_wrote_are_translations():
    # e.g. a name the AI kept as is; translating it again every run would
    # use up the word limit for nothing
    app = _make_app()
    app.get_module(0).name['fra'] = 'register module'
    fmt = AppTranslationFormat(app, 'fra', treat_default_copies_as_missing=True,
                               ai_translated_keys={MODULE_NAME_KEY})
    assert 'register module' not in {u.source_text for u in fmt.load_input().values()}


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


def test_for_app_copies_settings_not_state():
    app = _make_app()
    fmt = AppTranslationFormat(
        app, 'fra', mode=MODE_RETRANSLATE, manually_edited_keys={'k'},
        stale_keys={'s'}, treat_default_copies_as_missing=True, ai_translated_keys={'a'})
    fmt.load_input()
    fmt.results = {'0': 'traduction'}
    other_app = _make_app()

    copy = fmt.for_app(other_app)

    assert copy.app is other_app
    assert (copy.target_lang, copy.mode) == ('fra', MODE_RETRANSLATE)
    assert copy.manually_edited_keys == {'k'}
    assert copy.stale_keys == {'s'}
    assert copy.treat_default_copies_as_missing is True
    assert copy.ai_translated_keys == {'a'}
    assert (copy.units_by_id, copy.results, copy.skipped_ids) == ({}, {}, set())


def test_for_app_keeps_subclass():
    class CustomFormat(AppTranslationFormat):
        pass

    fmt = CustomFormat(_make_app(), 'fra')
    assert type(fmt.for_app(_make_app())) is CustomFormat


def _edit_module_name_source(app):
    app.get_module(0).name['en'] = 'enrol module'


def _fill_module_name_target(app):
    app.get_module(0).name['fra'] = 'mon module'


def _replace_question(app):
    xform = XFormBuilder()
    xform.new_question('age', {'en': 'How old?', 'fra': ''})
    app.get_module(0).get_form(0).source = xform.tostring().decode('utf-8')


def _add_module_first(app):
    factory = AppFactory(build_version='2.40.0')
    factory.app = app
    factory.new_basic_module('aaa_first', 'case')
    app.rearrange_modules(len(app.modules) - 1, 0)


@pytest.mark.parametrize("mode, change_app, dropped_source", [
    (MODE_FILL_MISSING, lambda app: None, None),
    (MODE_FILL_MISSING, _edit_module_name_source, 'register module'),
    (MODE_FILL_MISSING, _fill_module_name_target, 'register module'),
    (MODE_FILL_MISSING, _replace_question, 'What is the name?'),
    (MODE_FILL_MISSING, _add_module_first, None),  # unit ids shift; keys must not
    (MODE_RETRANSLATE, lambda app: None, None),
    # the string is still a unit, so only its changed target shows the edit
    (MODE_RETRANSLATE, _fill_module_name_target, 'register module'),
], ids=[
    'unchanged', 'source-edited', 'target-filled', 'row-gone', 'ids-shift',
    'retranslate-unchanged', 'retranslate-target-edited',
])
def test_rebase_results(mode, change_app, dropped_source):
    app = _make_app()
    stale_fmt = AppTranslationFormat(app, 'fra', mode=mode)
    stale_units = stale_fmt.load_input()
    stale_fmt.results = {
        uid: f'FR:{unit.source_text}' for uid, unit in stale_units.items()}

    change_app(app)
    fresh_fmt = AppTranslationFormat(app, 'fra', mode=mode)
    fresh_fmt.load_input()

    changed = _rebase_results(stale_fmt, fresh_fmt)

    assert changed == (0 if dropped_source is None else 1)
    assert len(fresh_fmt.results) == len(stale_units) - changed
    # every carried result landed on the unit it was translated from
    for fresh_id, translated in fresh_fmt.results.items():
        assert translated == f'FR:{fresh_fmt.units_by_id[fresh_id].source_text}'
    assert f'FR:{dropped_source}' not in fresh_fmt.results.values()


def test_rebase_results_keeps_stale_results():
    app = _make_app()
    app.get_module(0).name['fra'] = 'module inscription'
    stale_fmt = AppTranslationFormat(app, 'fra', stale_keys={MODULE_NAME_KEY})
    stale_fmt.results = {uid: 'FR' for uid in stale_fmt.load_input()}
    fresh_fmt = stale_fmt.for_app(app)
    fresh_fmt.load_input()

    changed = _rebase_results(stale_fmt, fresh_fmt)

    carried_keys = {fresh_fmt.units_by_id[uid].string_key for uid in fresh_fmt.results}
    assert changed == 0
    assert MODULE_NAME_KEY in carried_keys


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


class TestApplyTranslations(TestCase):
    """Conflicts are real: a second copy of the app is saved after the
    run's copy was read, so the run's ``app.save()`` fails its _rev check."""

    def _saved_app(self):
        app = _make_app()
        app.save()
        # refetch on cleanup: the local copy's _rev goes stale in these tests
        self.addCleanup(lambda: get_app(app.domain, app.get_id).delete())
        return app

    def _translated_fmt(self, app):
        fmt = AppTranslationFormat(app, 'fra')
        units = fmt.load_input()
        fmt.results = {uid: f'FR:{u.source_text}' for uid, u in units.items()}
        return fmt

    def _save_other_copy(self, app, change):
        other = get_app(app.domain, app.get_id)
        change(other)
        other.save()

    def _current(self, app):
        return get_app(app.domain, app.get_id)

    def test_no_conflict_saves_once_without_refetching(self):
        app = self._saved_app()
        fmt = self._translated_fmt(app)

        applied = _apply_translations(fmt)

        assert applied.saved_fmt is fmt
        assert applied.changed == 0
        assert applied.translated == len(fmt.results)
        assert self._current(app).get_module(0).name['fra'] == 'FR:register module'

    def test_conflict_with_unrelated_edit_keeps_both(self):
        app = self._saved_app()
        fmt = self._translated_fmt(app)
        self._save_other_copy(app, lambda other: setattr(other, 'name', 'Renamed'))

        applied = _apply_translations(fmt)

        current = self._current(app)
        assert applied.changed == 0
        assert current.name == 'Renamed'
        assert current.get_module(0).name['fra'] == 'FR:register module'
        assert applied.app_version == current.version

    def test_conflict_keeps_translation_the_user_typed(self):
        app = self._saved_app()
        fmt = self._translated_fmt(app)
        self._save_other_copy(app, _fill_module_name_target)

        applied = _apply_translations(fmt)

        current = self._current(app)
        assert applied.changed == 1
        assert current.get_module(0).name['fra'] == 'mon module'
        # everything else still landed
        assert AppTranslationFormat(current, 'fra').load_input() == {}

    def test_conflict_on_last_attempt_applies_nothing(self):
        app = self._saved_app()
        fmt = self._translated_fmt(app)
        self._save_other_copy(app, lambda other: setattr(other, 'name', 'Renamed'))

        with pytest.raises(AppChangedDuringTranslation):
            with patch.object(ai_translator, 'AI_TRANSLATION_APPLY_ATTEMPTS', 1):
                _apply_translations(fmt)

        assert self._current(app).get_module(0).name.get('fra', '') == ''

    def test_conflict_on_every_attempt_raises(self):
        app = self._saved_app()
        fmt = self._translated_fmt(app)
        self._save_other_copy(app, lambda other: setattr(other, 'name', 'Renamed'))

        def get_app_then_save_again(domain, app_id):
            fresh = get_app(domain, app_id)
            self._save_other_copy(fresh, lambda other: None)  # beats our save
            return fresh

        with (
            patch.object(ai_translator, 'get_app', get_app_then_save_again),
            patch.object(ai_translator, 'AI_TRANSLATION_APPLY_ATTEMPTS', 2),
            pytest.raises(AppChangedDuringTranslation),
        ):
            _apply_translations(fmt)

        assert self._current(app).get_module(0).name.get('fra', '') == ''


class TestRecordRun(TestCase):

    def test_records_provenance_and_usage(self):
        app = _make_app()
        fmt = AppTranslationFormat(app, 'fra')
        units = fmt.load_input()

        # the AI returned translations for two of the five units we sent
        fmt.results = {
            uid: f'FR:{unit.source_text}' for uid, unit in units.items()
            if unit.string_key in (MODULE_NAME_KEY, QUESTION_KEY)
        }
        fmt.save_output()
        self.addCleanup(app.delete)

        _record_run(fmt, strings_attempted=5, model='gpt-4.1')

        usage = AITranslationUsage.objects.get(app_id=app.get_id)
        assert model_to_dict(usage, exclude=['id']) == {
            'domain': app.domain,
            'app_id': app.get_id,
            'lang': 'fra',
            'strings_attempted': 5,
            'strings_translated': 2,
            'words_translated': 6,  # "register module", "What is the name?"
            'total_app_strings': len(ALL_STRING_KEYS),
            'total_app_strings_ai_translated': 2,
            'app_version': app.version,
            'model': 'gpt-4.1',
        }
        assert set(AITranslation.objects.filter(app_id=app.get_id).values_list(
            'string_key', 'translated_value', 'status',
        )) == {
            (MODULE_NAME_KEY, 'FR:register module', AITranslation.STATUS_APPLIED),
            (QUESTION_KEY, 'FR:What is the name?', AITranslation.STATUS_APPLIED),
        }

    def test_stores_values_as_the_app_holds_them(self):
        app = _make_app()
        fmt = AppTranslationFormat(app, 'fra')
        units = fmt.load_input()
        translations = {
            MODULE_NAME_KEY: 'Sel & poivre',  # a JSON string on the app
            QUESTION_KEY: 'Quel <b>nom</b> & prénom ?',  # form XML
        }
        fmt.results = {
            uid: translations[unit.string_key] for uid, unit in units.items()
            if unit.string_key in translations
        }
        fmt.save_output()
        self.addCleanup(app.delete)

        _record_run(fmt, strings_attempted=2, model='gpt-4.1')

        assert dict(
            AITranslation.objects.filter(app_id=app.get_id).values_list('source_value', 'translated_value')
        ) == {
            'register module': 'Sel & poivre',
            'What is the name?': 'Quel &lt;b&gt;nom&lt;/b&gt; &amp; prénom ?',
        }
        usage = AITranslationUsage.objects.get(app_id=app.get_id)
        assert usage.total_app_strings_ai_translated == 2
        # the next run sees them as untouched AI translations
        assert find_changed_ai_translations(AppTranslationFormat(app, 'fra')) == (
            ChangedAITranslations(manually_edited=set(), stale=set()))

    def test_unapplied_result_keeps_the_string_stale(self):
        app = _make_app()
        app.get_module(0).name['fra'] = AI_TRANSLATION
        app.save()
        self.addCleanup(app.delete)
        # earlier run would have recorded this AI Translation
        _record_ai_translation(app, MODULE_NAME_KEY, AI_SOURCE, AI_TRANSLATION)

        # the module name's AI translation goes stale when its source text changes
        app.get_module(0).name['en'] = 'New Module Name'
        fmt = AppTranslationFormat(app, 'fra', stale_keys={MODULE_NAME_KEY})
        uids = {u.string_key: uid for uid, u in fmt.load_input().items()}

        # the AI retranslated it, but save_output() never applied the result,
        # so the app still holds the old translation
        fmt.results = {uids[MODULE_NAME_KEY]: 'nouveau module'}

        _record_run(fmt, strings_attempted=1, model='gpt-4.1')

        assert AITranslationUsage.objects.get(app_id=app.get_id).strings_translated == 0
        row = AITranslation.objects.get(app_id=app.get_id, string_key=MODULE_NAME_KEY)
        assert (row.source_value, row.translated_value) == (AI_SOURCE, AI_TRANSLATION)
        # so the next run still sees it as stale and retranslates it
        assert find_changed_ai_translations(AppTranslationFormat(app, 'fra')).stale == {MODULE_NAME_KEY}


class _FakeTranslator:
    """Translates every batch by prefixing 'FR:', failing when asked.
    ``on_translate`` runs before each batch."""
    model = 'fake-model'

    def __init__(self, fmt, fail_batches=(), fail_all=False, on_translate=None):
        self.fmt = fmt
        self.fail_batches = set(fail_batches)
        self.fail_all = fail_all
        self.on_translate = on_translate
        self.calls = 0

    def translate(self, batch):
        self.calls += 1
        if self.on_translate:
            self.on_translate()
        if self.fail_all or self.calls in self.fail_batches:
            raise Exception('LLM exploded')
        return self.fmt.parse_output(json.dumps(
            {uid: f'FR:{unit.source_text}' for uid, unit in batch.items()}))


class TestRunAppTranslation(TestCase):

    def test_full_success(self):
        app = _make_app()
        fmt = AppTranslationFormat(app, 'fra')
        summary = run_app_translation(
            app, 'fra', MODE_FILL_MISSING, translation_format=fmt,
            translator=_FakeTranslator(fmt), chunk_size=2)
        assert summary == {
            'total': 5, 'translated': 5, 'skipped': 0, 'changed': 0, 'failed': 0,
            'app_version': app.version, 'errors': []}
        assert app.get_module(0).name['fra'] == 'FR:register module'

    def test_partial_apply_on_batch_failure(self):
        app = _make_app()
        fmt = AppTranslationFormat(app, 'fra')
        summary = run_app_translation(
            app, 'fra', MODE_FILL_MISSING, translation_format=fmt,
            translator=_FakeTranslator(fmt, fail_batches={1}), chunk_size=2)
        # first batch of 2 failed; remaining 3 strings applied
        assert summary['total'] == 5
        assert summary['translated'] == 3
        assert summary['failed'] == 2
        assert summary['skipped'] == 0

    def test_nothing_to_translate(self):
        app = _make_app()
        # first run translates everything ...
        fmt = AppTranslationFormat(app, 'fra')
        run_app_translation(app, 'fra', MODE_FILL_MISSING, translation_format=fmt,
                            translator=_FakeTranslator(fmt), chunk_size=50)
        # ... so a fill_missing re-run finds nothing and makes no LLM calls
        fmt2 = AppTranslationFormat(app, 'fra')
        translator2 = _FakeTranslator(fmt2)
        summary = run_app_translation(app, 'fra', MODE_FILL_MISSING,
                                      translation_format=fmt2, translator=translator2)
        assert summary['total'] == 0
        assert summary['translated'] == 0
        assert translator2.calls == 0

    def _run(self, app, **translator_kwargs):
        return run_app_translation(
            app, 'fra', MODE_FILL_MISSING, chunk_size=50,
            translator_factory=lambda lang, fmt, **kw: _FakeTranslator(fmt, **translator_kwargs))

    def test_next_run_skips_edits_and_retranslates_stale_strings(self):
        app = _make_app()
        self._run(app)
        app.get_module(0).name['fra'] = 'mon module'  # manual edit
        app.get_module(0).get_form(0).name['en'] = 'enrol form'  # AI text goes stale

        # Second run: the module name should be skipped,
        # the form name should be retranslated
        summary = self._run(app)

        assert summary['total'] == 1
        assert app.get_module(0).name['fra'] == 'mon module'
        assert app.get_module(0).get_form(0).name['fra'] == 'FR:enrol form'

        usage = AITranslationUsage.objects.filter(app_id=app.get_id).latest('created_on')
        # Only the form's name was retranslated;
        # the module's name was skipped because it was manually edited
        assert (usage.strings_attempted, usage.strings_translated, usage.model) == (1, 1, 'fake-model')
        # the first run's 5, less the edited module name
        assert usage.total_app_strings_ai_translated == 4

        statuses = dict(
            AITranslation.objects.filter(app_id=app.get_id).values_list('string_key', 'status'))
        assert statuses[MODULE_NAME_KEY] == AITranslation.STATUS_MANUALLY_EDITED
        # applied only if the row now holds the retranslation
        assert statuses[FORM_NAME_KEY] == AITranslation.STATUS_APPLIED
        # and the new source, so the next run doesn't see it as stale again
        assert AITranslation.objects.get(
            app_id=app.get_id, string_key=FORM_NAME_KEY).source_value == 'enrol form'

    def test_user_edit_during_run_drops_that_result(self):
        app = _make_app()
        app.save()
        self.addCleanup(app.delete)
        # an AI translation since cleared, so this run translates it again
        _record_ai_translation(app, MODULE_NAME_KEY, AI_SOURCE, AI_TRANSLATION)

        def user_types_module_name():
            other = get_app(app.domain, app.get_id)
            _fill_module_name_target(other)
            other.save()

        summary = self._run(app, on_translate=user_types_module_name)

        assert summary['changed'] == 1, "expected the user's edit to win"
        assert summary['translated'] == 4, 'expected the other 4 results to be saved'
        usage = AITranslationUsage.objects.get(app_id=app.get_id)
        assert usage.strings_translated == summary['translated']
        row = AITranslation.objects.get(app_id=app.get_id, string_key=MODULE_NAME_KEY)
        assert row.status == AITranslation.STATUS_MANUALLY_EDITED
        # still the earlier AI translation; this run's 'FR:register module' was dropped
        assert row.translated_value == AI_TRANSLATION

    def test_records_nothing_when_nothing_is_applied(self):
        app = _make_app()

        summary = self._run(app, fail_all=True)

        assert summary['translated'] == 0
        assert not AITranslationUsage.objects.filter(app_id=app.get_id).exists()
        assert not AITranslation.objects.filter(app_id=app.get_id).exists()
