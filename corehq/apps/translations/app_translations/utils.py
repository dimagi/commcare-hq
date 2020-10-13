from hashlib import md5
import os
from django.contrib import messages
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    ModuleNotFoundException,
)
from corehq.apps.translations.const import (
    MODULES_AND_FORMS_SHEET_NAME,
    SINGLE_SHEET_NAME,
    SINGLE_SHEET_STATIC_HEADERS,
)
from corehq.apps.translations.generators import EligibleForTransifexChecker


def get_bulk_app_sheet_headers(app, single_sheet=False, lang=None, eligible_for_transifex_only=False,
                               by_id=False):
    '''
    Returns lists representing the expected structure of bulk app translation
    Excel file uploads and downloads.

    The list will be in the form:
    [
        ["sheetname", ["column name1", "column name 2"]],
        ["sheet2 name", [...]],
        ...
    ]

    `eligible_for_transifex_only` will skip modules and forms that have "SKIP
    TRANSIFEX" in their comment.
    '''
    langs = [lang] if lang else app.langs

    default_lang_list = ['default_' + l for l in langs]
    audio_lang_list = ['audio_' + l for l in langs]
    image_lang_list = ['image_' + l for l in langs]
    video_lang_list = ['video_' + l for l in langs]
    lang_list = default_lang_list + image_lang_list + audio_lang_list + video_lang_list

    if single_sheet:
        return ((SINGLE_SHEET_NAME, tuple(
            SINGLE_SHEET_STATIC_HEADERS
        ) + tuple(lang_list) + ('unique_id',)),)

    headers = []

    # Add headers for the first sheet
    headers.append([
        MODULES_AND_FORMS_SHEET_NAME,
        get_modules_and_forms_row(
            row_type='Type',
            sheet_name='menu_or_form',
            languages=default_lang_list,
            media_image=['image_%s' % l for l in langs],
            media_audio=['audio_%s' % l for l in langs],
            unique_id='unique_id',
        )
    ])

    for module in app.get_modules():
        if eligible_for_transifex_only and EligibleForTransifexChecker.exclude_module(module):
            continue

        sheet_name = module.unique_id if by_id else get_module_sheet_name(module)
        headers.append([sheet_name, ['case_property', 'list_or_detail'] + default_lang_list])

        for form in module.get_forms():
            if form.form_type == 'shadow_form':
                continue
            if eligible_for_transifex_only and EligibleForTransifexChecker.exclude_form(form):
                continue

            sheet_name = form.unique_id if by_id else get_form_sheet_name(form)
            headers.append([sheet_name, ["label"] + lang_list])
    return headers


def get_modules_and_forms_row(row_type, sheet_name, languages, media_image, media_audio, unique_id):
    """
    Assemble the various pieces of data that make up a row in the
    modules and forms sheet sheet into a single row (a flat tuple).

    This function is meant as the single point of truth for the
    column ordering of this sheet.

    """
    assert row_type is not None
    assert sheet_name is not None
    assert isinstance(languages, list)
    assert isinstance(media_image, list)
    assert isinstance(media_audio, list)
    assert isinstance(unique_id, str), type(unique_id)

    return [item if item is not None else ""
            for item in (
                [row_type, sheet_name]
                + get_menu_row(languages, media_image, media_audio)
                + [unique_id])]


def get_menu_row(languages, media_image, media_audio):
    return languages + media_image + media_audio


def get_module_sheet_name(module):
    return "menu{}".format(module.get_app().get_module_index(module.unique_id) + 1)


def get_form_sheet_name(form):
    module = form.get_module()
    return "_".join([
        get_module_sheet_name(module),
        "form{}".format(module.get_form_index(form.unique_id) + 1)
    ])


def is_form_sheet(identifier):
    return 'menu' in identifier and 'form' in identifier


def is_module_sheet(identifier):
    return 'menu' in identifier and 'form' not in identifier


def is_modules_and_forms_sheet(identifier):
    return identifier == MODULES_AND_FORMS_SHEET_NAME


def is_single_sheet(identifier):
    return identifier == SINGLE_SHEET_NAME


def is_single_sheet_workbook(workbook):
    sheets_count = len(workbook.worksheets)

    first_sheet = workbook.worksheets[0]
    if sheets_count == 1 and is_single_sheet(first_sheet.title):
        return True

    return False


def get_menu_or_form_by_sheet_name(app, sheet_name):
    if '_' in sheet_name:
        return get_form_from_sheet_name(app, sheet_name)
    else:
        return get_module_from_sheet_name(app, sheet_name)


def get_menu_or_form_by_unique_id(app, unique_id, sheet_name):
    if is_form_sheet(sheet_name):
        try:
            return app.get_form(unique_id)
        except FormNotFoundException:
            raise FormNotFoundException(_('Invalid form in row "%s", skipping row.') % sheet_name)
    elif is_module_sheet(sheet_name):
        try:
            return app.get_module_by_unique_id(unique_id)
        except ModuleNotFoundException:
            raise ModuleNotFoundException(_('Invalid menu in row "%s", skipping row.') % sheet_name)
    else:
        raise ValueError(_('Did not recognize "%s", skipping row.') % sheet_name)


def get_module_from_sheet_name(app, identifier):
    module_index = int(identifier.replace("menu", "")) - 1
    try:
        return app.get_module(module_index)
    except ModuleNotFoundException:
        raise ModuleNotFoundException(_('Invalid menu in row "%s", skipping row.') % identifier)


def get_form_from_sheet_name(app, identifier):
    try:
        mod_text, form_text = identifier.split("_")
    except ValueError:
        raise ValueError(_('Did not recognize "%s", skipping row.') % identifier)
    module = get_module_from_sheet_name(app, mod_text)
    form_index = int(form_text.replace("form", "")) - 1
    try:
        return module.get_form(form_index)
    except FormNotFoundException:
        raise FormNotFoundException(_('Invalid form in row "%s", skipping row.') % identifier)


def get_unicode_dicts(iterable):
    """
    Iterates iterable and returns a list of dictionaries with keys and values converted to Unicode

    >>> gen = ({'0': None, 2: 'two', u'3': 0xc0ffee} for i in range(3))
    >>> get_unicode_dicts(gen)
    [{u'2': u'two', u'0': None, u'3': u'12648430'},
     {u'2': u'two', u'0': None, u'3': u'12648430'},
     {u'2': u'two', u'0': None, u'3': u'12648430'}]

    """
    def none_or_unicode(val):
        return str(val) if val is not None else val

    rows = []
    for row in iterable:
        rows.append({str(k): none_or_unicode(v) for k, v in row.items()})
    return rows


def text_and_audio_changed(current_row, previous_row, headers):
    text_changed = False
    audio_path_changed = False
    for index, header in enumerate(headers):
        if "default_" in header and previous_row[index] != current_row[header]:
            text_changed = True
        if "audio_" in header and previous_row[index] != current_row[header]:
            audio_path_changed = True
    return text_changed, audio_path_changed


def generate_audio_path(text, lang, previous_path):
    path_hash = md5(f'{text}_{lang}'.encode()).hexdigest()[:6]
    file_path_arr = previous_path.split('/')
    filename_index = len(file_path_arr) - 1
    complete_filename, extension = os.path.splitext(os.path.basename(previous_path))
    filename_arr = complete_filename.split('-')
    filename_arr[len(filename_arr) - 1] = path_hash
    new_filename = '-'.join(filename_arr) + extension
    file_path_arr[filename_index] = new_filename
    return '/'.join(file_path_arr)


def update_audio_path_if_required(current_row, previous_row, headers, langs):
    '''
    Compares the uploaded row with one already present on app, if text and audio path
    both are changes it will return a Django error message format and if only text is
    updated it will create a new audio path for that particular language.
    '''
    text_changed, audio_path_changed = text_and_audio_changed(current_row, previous_row, headers)
    if text_changed and audio_path_changed:
        return (messages.error, _(
            f"You cannot update text and audio path simulatenouly for label {current_row['label']}"
        ))
    for lang in langs:
        audio_header = 'audio_%s' % lang
        if audio_header in current_row:
            audio_path = current_row[audio_header]
            if text_changed:
                new_audio_path = generate_audio_path(current_row[f'default_{lang}'], lang, audio_path)
                current_row[audio_header] = new_audio_path


class BulkAppTranslationUpdater(object):
    '''
        Class to help translate a particular model (app, module, or form).
    '''

    def __init__(self, app, lang=None):
        '''
        :param lang: If present, translation is limited to this language. This should correspond to the sheet
            only containing headers of this language, but having the language available is handy.
        '''
        super(BulkAppTranslationUpdater, self).__init__()
        self.app = app
        self.langs = [lang] if lang else app.langs
        self.is_multi_sheet = not bool(lang)

        # These attributes get populated by update
        self.msgs = None

    def update_translation_dict(self, prefix, language_dict, row):
        # update translations as requested
        for lang in self.langs:
            key = '%s%s' % (prefix, lang)
            if key not in row:
                continue
            translation = row[key]
            if translation:
                language_dict[lang] = translation
            else:
                language_dict.pop(lang, None)

        # delete anything in language_dict that isn't in app's langs (anymore)
        if self.is_multi_sheet:
            for lang in list(language_dict.keys()):
                if lang not in self.app.langs:
                    language_dict.pop(lang, None)

    def update(self, rows):
        '''
        Modify the translations of this updater's model given a sheet of translation data.
        This does not save the changes to the DB.

        :param rows: Iterable of rows from a WorksheetJSONReader
        :return:  Returns a list of message tuples. The first item in each tuple is
        a function like django.contrib.messages.error, and the second is a string.
        '''
        raise NotImplementedError()
