# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import six
from django.contrib import messages
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.const import APP_TRANSLATION_UPLOAD_FAIL_MESSAGE
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME, SINGLE_SHEET_NAME
from corehq.util.workbook_json.excel import HeaderValueError, WorkbookJSONReader, JSONReaderError, \
    InvalidExcelFileException



def get_app_translation_workbook(file_or_filename):
    msgs = []
    try:
        workbook = WorkbookJSONReader(file_or_filename)
    # todo: HeaderValueError does not belong here
    except (HeaderValueError, InvalidExcelFileException) as e:
        msgs.append(
            (messages.error, _(APP_TRANSLATION_UPLOAD_FAIL_MESSAGE).format(e))
        )
        return False, msgs
    except JSONReaderError as e:
        msgs.append(
            (messages.error, _(
                "App Translation Failed! There is an issue with Excel columns. Error details: {}."
            ).format(e))
        )
        return False, msgs
    return workbook, msgs


def get_bulk_app_sheet_headers(app, lang=None, exclude_module=None, exclude_form=None):
    '''
    Returns lists representing the expected structure of bulk app translation
    Excel file uploads and downloads.

    The list will be in the form:
    [
        ["sheetname", ["column name1", "column name 2"]],
        ["sheet2 name", [...]],
        ...
    ]

    exclude_module and exclude_form are functions that take in one argument
    (form or module) and return True if the module/form should be excluded
    from the returned list
    '''
    langs = [lang] if lang else app.langs

    default_lang_list = ['default_' + l for l in langs]
    audio_lang_list = ['audio_' + l for l in langs]
    image_lang_list = ['image_' + l for l in langs]
    video_lang_list = ['video_' + l for l in langs]
    lang_list = default_lang_list + image_lang_list + audio_lang_list + video_lang_list

    if lang:
        return ((SINGLE_SHEET_NAME, (
            'menu or form',
            'case_property',         # modules only
            'detail or label',       # detail type (module) or question label (form)
        ) + tuple(lang_list)),)

    headers = []

    # Add headers for the first sheet
    headers.append([
        MODULES_AND_FORMS_SHEET_NAME,
        get_modules_and_forms_row(
            row_type='Type',
            sheet_name='sheet_name',
            languages=default_lang_list,
            media_image=['icon_filepath_%s' % l for l in langs],
            media_audio=['audio_filepath_%s' % l for l in langs],
            unique_id='unique_id',
        )
    ])

    for mod_index, module in enumerate(app.get_modules()):
        if exclude_module is not None and exclude_module(module):
            continue

        sheet_name = get_module_sheet_name(module)
        headers.append([sheet_name, ['case_property', 'list_or_detail'] + default_lang_list])

        for form_index, form in enumerate(module.get_forms()):
            if form.form_type == 'shadow_form':
                continue
            if exclude_form is not None and exclude_form(form):
                continue

            sheet_name = get_form_sheet_name(form)
            headers.append([
                sheet_name,
                ["label"] + lang_list
            ])
    return headers


def get_modules_and_forms_row(row_type, sheet_name, languages, media_image, media_audio, unique_id):
    """
    assemble the various pieces of data that make up a row in the
    {sheet_name} sheet into a single row (a flat tuple).

    This function is meant as the single point of truth for the
    column ordering of {sheet_name}

    """.format(sheet_name=MODULES_AND_FORMS_SHEET_NAME)
    assert row_type is not None
    assert sheet_name is not None
    assert isinstance(languages, list)
    assert isinstance(media_image, list)
    assert isinstance(media_audio, list)
    assert isinstance(unique_id, six.string_types)
    soft_assert_type_text(unique_id)

    return [item if item is not None else "" for item in
            ([row_type, sheet_name] +
             get_menu_row(languages, media_image, media_audio) +
             [unique_id])]


def get_menu_row(languages, media_image, media_audio):
    return languages + media_image + media_audio


def get_module_sheet_name(module):
    return "module{}".format(module.get_app().get_module_index(module.unique_id) + 1)


def get_form_sheet_name(form):
    module = form.get_module()
    return "_".join([
        get_module_sheet_name(module),
        "form{}".format(module.get_form_index(form.unique_id) + 1)
    ])


def is_form_sheet(sheet):
    return 'module' in sheet.worksheet.title and 'form' in sheet.worksheet.title


def is_module_sheet(sheet):
    return 'module' in sheet.worksheet.title and 'form' not in sheet.worksheet.title


def is_modules_and_forms_sheet(sheet):
    return sheet.worksheet.title == MODULES_AND_FORMS_SHEET_NAME


def is_single_sheet(sheet):
    return sheet.worksheet.title == SINGLE_SHEET_NAME


def get_missing_cols(app, sheet, headers):
    expected_sheets = {h[0]: h[1] for h in headers}
    expected_columns = expected_sheets.get(sheet.worksheet.title, None)
    return set(expected_columns) - set(sheet.headers)


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
        return six.text_type(val) if val is not None else val

    rows = []
    for row in iterable:
        rows.append({six.text_type(k): none_or_unicode(v) for k, v in six.iteritems(row)})
    return rows


def update_translation_dict(prefix, language_dict, row, langs):
    # update translations as requested
    for lang in langs:
        key = '%s%s' % (prefix, lang)
        if key not in row:
            continue
        translation = row[key]
        if translation:
            language_dict[lang] = translation
        else:
            language_dict.pop(lang, None)

    # delete anything in language_dict that isn't in langs (anymore)
    for lang in language_dict.keys():
        if lang not in langs:
            language_dict.pop(lang, None)
