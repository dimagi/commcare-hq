# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import six
from django.contrib import messages
from django.utils.text import slugify
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.const import APP_TRANSLATION_UPLOAD_FAIL_MESSAGE
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.apps.translations.const import (
    LEGACY_MODULES_AND_FORMS_SHEET_NAME,
    MODULES_AND_FORMS_SHEET_NAME,
    SINGLE_SHEET_NAME,
)
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
            'menu_or_form',
            'case_property',        # modules only
            'list_or_detail',       # modules only
            'label',                # forms only
        ) + tuple(lang_list)),)

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
        if exclude_module is not None and exclude_module(module):
            continue

        sheet_name = get_module_sheet_name(app, module)
        headers.append([sheet_name, ['case_property', 'list_or_detail'] + default_lang_list])

        for form in module.get_forms():
            if form.form_type == 'shadow_form':
                continue
            if exclude_form is not None and exclude_form(form):
                continue

            sheet_name = get_form_sheet_name(app, form)
            headers.append([
                sheet_name,
                ["label"] + lang_list
            ])
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
    assert isinstance(unique_id, six.string_types)
    soft_assert_type_text(unique_id)

    return [item if item is not None else "" for item in
            ([row_type, sheet_name] +
             get_menu_row(languages, media_image, media_audio) +
             [unique_id])]


def get_menu_row(languages, media_image, media_audio):
    return languages + media_image + media_audio


def get_module_sheet_name(app, module):
    """
    Returns 'slug:m:UUID'

    The UUID uniquely identifies the module even if it moves. The slug
    makes it readable by (English-reading) humans.
    """
    return '{slug}:m:{uuid}'.format(slug=get_name_slug(app, module), uuid=module.unique_id)


def get_form_sheet_name(app, form):
    """
    Returns 'slug:f:UUID'

    The UUID uniquely identifies the form even if it moves. The slug
    makes it readable by humans.
    """
    return '{slug}:f:{uuid}'.format(slug=get_name_slug(app, form), uuid=form.unique_id)


def get_name_slug(app, module_or_form):
    name_dict = module_or_form.name
    if app.default_language in name_dict:
        name = name_dict[app.default_language]
    elif name_dict:
        name = list(name_dict.values())[0]
    else:
        name = ''
    return slugify(name)


def is_form_sheet(identifier):
    return ':f:' in identifier


def is_module_sheet(identifier):
    return ':m:' in identifier


def get_module_or_form(app, identifier):
    if is_legacy_module_sheet(identifier) or is_legacy_form_sheet(identifier):
        return get_module_or_form_by_legacy_identifier(app, identifier)
    slug, m_or_f, unique_id = identifier.split(':')
    if m_or_f == 'm':
        return app.get_module_by_unique_id(unique_id)
    if m_or_f == 'f':
        return app.get_form(unique_id)
    raise ValueError('Unrecognized identifier format "{}"'.format(identifier))


def is_modules_and_forms_sheet(identifier):
    return identifier == MODULES_AND_FORMS_SHEET_NAME or identifier == LEGACY_MODULES_AND_FORMS_SHEET_NAME


def is_single_sheet(identifier):
    return identifier == SINGLE_SHEET_NAME


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


class BulkAppTranslationUpdater(object):
    '''
        Class to help translatea particular model (app, module, or form).
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


# TODO: (2019-04-26) Drop support for legacy names after all translations could possibly have been uploaded
#
def get_legacy_name_map(app, exclude_module=None, exclude_form=None):
    """
    Maps legacy module and form sheet names to current names
    """
    name_map = {}
    for module in app.get_modules():
        if exclude_module is not None and exclude_module(module):
            continue
        legacy_name = get_module_legacy_sheet_name(module)
        name_map[legacy_name] = get_module_sheet_name(app, module)

        for form in module.get_forms():
            if exclude_form is not None and exclude_form(form):
                continue
            legacy_name = get_form_legacy_sheet_name(form)
            name_map[legacy_name] = get_form_sheet_name(app, form)

    return name_map


def get_module_legacy_sheet_name(module):
    """
    Returns "menuN" where N was its (1-based) index.

    Breaks if module is moved. Use get_module_sheet_name() instead.
    """
    return "menu{}".format(module.get_app().get_module_index(module.unique_id) + 1)


def get_form_legacy_sheet_name(form):
    """
    Returns "menuM_formN" where N was its (1-based) index.

    Breaks if form or module is moved. Use get_form_sheet_name() instead.
    """
    module = form.get_module()
    return "_".join([
        get_module_sheet_name(module),
        "form{}".format(module.get_form_index(form.unique_id) + 1)
    ])


def is_legacy_form_sheet(identifier):
    return ('module' in identifier or 'menu' in identifier) and 'form' in identifier


def is_legacy_module_sheet(identifier):
    return ('module' in identifier or 'menu' in identifier) and 'form' not in identifier


def get_module_or_form_by_legacy_identifier(app, identifier):
    if '_' in identifier:
        return get_form_by_legacy_identifier(app, identifier)
    else:
        return get_module_by_legacy_identifier(app, identifier)


def get_module_by_legacy_identifier(app, identifier):
    module_index = int(identifier.replace("menu", "").replace("module", "")) - 1
    return app.get_module(module_index)


def get_form_by_legacy_identifier(app, identifier):
    identifying_parts = identifier.split('_')
    if len(identifying_parts) != 2:
        raise ValueError
    module = get_module_by_legacy_identifier(app, identifying_parts[0])
    form_index = int(identifying_parts[1].replace("form", "")) - 1
    return module.get_form(form_index)
