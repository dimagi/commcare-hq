from lxml import etree
import copy

from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    ModuleNotFoundException,
)
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import namespaces, WrappedNode
from dimagi.utils.excel import WorkbookJSONReader, HeaderValueError

from django.contrib import messages
from django.utils.translation import ugettext as _


def process_bulk_app_translation_upload(app, f):
    """
    Process the bulk upload file for the given app.
    We return these message tuples instead of calling them now to allow this
    function to be used independently of request objects.

    :param app:
    :param f:
    :return: Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """

    msgs = []

    headers = expected_bulk_app_sheet_headers(app)
    expected_sheets = {h[0]: h[1] for h in headers}
    processed_sheets = set()

    try:
        workbook = WorkbookJSONReader(f)
    except HeaderValueError, e:
        msgs.append(
            (messages.error, _("App Translation Failed! " + str(e)))
        )
        return msgs

    for sheet in workbook.worksheets:
        # sheet.__iter__ can only be called once, so cache the result
        rows = [row for row in sheet]
        # Convert every key and value to a string
        for i in xrange(len(rows)):
            rows[i] = {unicode(k): unicode(v) for k, v in rows[i].iteritems()}

        # CHECK FOR REPEAT SHEET
        if sheet.worksheet.title in processed_sheets:
            msgs.append((
                messages.error,
                'Sheet "%s" was repeated. Only the first ' +
                'occurrence has been processed' %
                sheet.worksheet.title
            ))
            continue

        # CHECK FOR BAD SHEET NAME
        expected_columns = expected_sheets.get(sheet.worksheet.title, None)
        if expected_columns is None:
            msgs.append((
                messages.error,
                'Skipping sheet "%s", did not recognize title' %
                sheet.worksheet.title
            ))
            continue

        # CHECK FOR MISSING KEY COLUMN
        if sheet.worksheet.title == "Modules and Forms":
            # Several columns on this sheet could be used to uniquely identify
            # rows. Using sheet_name for now, but unique_id could also be used.
            if expected_columns[1] not in sheet.headers:
                msgs.append((
                    messages.error,
                    'Skipping sheet "%s", could not find "%s" column' %
                    (sheet.worksheet.title, expected_columns[1])
                ))
                continue
        elif expected_columns[0] == "case_property":
            # It's a module sheet
            if (expected_columns[0] not in sheet.headers
                    or expected_columns[1] not in sheet.headers):
                msgs.append((
                    messages.error,
                    'Skipping sheet "%s", could not find case_property'
                    ' or list_or_detail column.' % sheet.worksheet.title
                ))
                continue
        else:
            # It's a form sheet
            if expected_columns[0] not in sheet.headers:
                msgs.append((
                    messages.error,
                    'Skipping sheet "%s", could not find label columns' %
                    sheet.worksheet.title
                ))
                continue

        processed_sheets.add(sheet.worksheet.title)

        # CHECK FOR MISSING COLUMNS
        missing_cols = set(expected_columns) - set(sheet.headers)
        if len(missing_cols) > 0:
            msgs.append((
                messages.warning,
                'Sheet "%s" has less columns than expected. '
                'Sheet will be processed but the following'
                ' translations will be unchanged: %s'
                % (sheet.worksheet.title, " ,".join(missing_cols))
            ))

        # CHECK FOR EXTRA COLUMNS
        extra_cols = set(sheet.headers) - set(expected_columns)
        if len(extra_cols) > 0:
            msgs.append((
                messages.warning,
                'Sheet "%s" has unrecognized columns. '
                'Sheet will be processed but ignoring the following columns: %s'
                % (sheet.worksheet.title, " ,".join(extra_cols))
            ))

        # NOTE: At the moment there is no missing row detection.
        # This could be added if we want though
        #      (it is not that bad if a user leaves out a row)

        if sheet.worksheet.title == "Modules_and_forms":
            # It's the first sheet
            ms = process_modules_and_forms_sheet(rows, app)
            msgs.extend(ms)
        elif sheet.headers[0] == "case_property":
            # It's a module sheet
            ms = update_case_list_translations(sheet, rows, app)
            msgs.extend(ms)
        else:
            # It's a form sheet
            ms = update_form_translations(sheet, rows, missing_cols, app)
            msgs.extend(ms)

    msgs.append(
        (messages.success, _("App Translations Updated!"))
    )
    return msgs


def expected_bulk_app_sheet_headers(app):
    '''
    Returns lists representing the expected structure of bulk app translation
    excel file uploads.

    The list will be in the form:
    [
        ["sheetname", ["column name1", "column name 2"]],
        ["sheet2 name", [...]],
        ...
    ]
    :param app:
    :return:
    '''
    languages_list = ['default_' + l for l in app.langs]
    audio_lang_list = ['audio_' + l for l in app.langs]
    image_lang_list = ['image_' + l for l in app.langs]
    video_lang_list = ['video_' + l for l in app.langs]

    headers = []

    # Add headers for the first sheet
    headers.append(
        ["Modules_and_forms",
            ['Type', 'sheet_name'] + languages_list +
            ['label_for_cases_%s' % l for l in app.langs] +
            ['icon_filepath', 'audio_filepath', 'unique_id']]
    )

    for mod_index, module in enumerate(app.get_modules()):

        module_string = "module" + str(mod_index + 1)
        headers.append([module_string, ['case_property', 'list_or_detail'] + languages_list])

        for form_index, form in enumerate(module.get_forms()):
            form_string = module_string + "_form" + str(form_index + 1)
            headers.append([
                form_string,
                ["label"] + languages_list + audio_lang_list + image_lang_list
                                                             + video_lang_list
            ])
    return headers


def process_modules_and_forms_sheet(rows, app):
    """
    Modify the translations and media references for the modules and forms in
    the given app as per the data provided in rows.
    This does not save the changes to the database.
    :param rows:
    :param app:
    :return:  Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    msgs = []

    for row in rows:
        identifying_text = row.get('sheet_name', '').split('_')

        if len(identifying_text) not in (1, 2):
            msgs.append((
                messages.error,
                'Invalid sheet_name "%s", skipping row.' % row.get(
                    'sheet_name', ''
                )
            ))
            continue

        module_index = int(identifying_text[0].replace("module", "")) - 1
        try:
            document = app.get_module(module_index)
        except ModuleNotFoundException:
            msgs.append((
                messages.error,
                'Invalid module in row "%s", skipping row.' % row.get(
                    'sheet_name'
                )
            ))
            continue
        if len(identifying_text) == 2:
            form_index = int(identifying_text[1].replace("form", "")) - 1
            try:
                document = document.get_form(form_index)
            except FormNotFoundException:
                msgs.append((
                    messages.error,
                    'Invalid form in row "%s", skipping row.' % row.get(
                        'sheet_name'
                    )
                ))
                continue

        if has_at_least_one_translation(row, 'default', app.langs):
            for lang in app.langs:
                translation = row['default_%s' % lang]
                if translation:
                    document.name[lang] = translation
                else:
                    document.name.pop(lang, None)

        if (has_at_least_one_translation(row, 'label_for_cases', app.langs)
                and hasattr(document, 'case_label')):
            for lang in app.langs:
                translation = row['label_for_cases_%s' % lang]
                if translation:
                    document.case_label[lang] = translation
                else:
                    document.case_label.pop(lang, None)

        image = row.get('icon_filepath', None)
        audio = row.get('audio_filepath', None)
        if image == '':
            image = None
        if audio == '':
            audio = None
        document.media_image = image
        document.media_audio = audio
    return msgs


def update_form_translations(sheet, rows, missing_cols, app):
    """
    Modify the translations of a form given a sheet of translation data.
    This does not save the changes to the DB.

    :param sheet: a WorksheetJSONReader
    :param rows: The rows of the sheet (we can't get this from the sheet
    because sheet.__iter__ can only be called once)
    :param missing_cols:
    :param app:
    :return:  Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    msgs = []
    mod_text, form_text = sheet.worksheet.title.split("_")
    module_index = int(mod_text.replace("module", "")) - 1
    form_index = int(form_text.replace("form", "")) - 1
    form = app.get_module(module_index).get_form(form_index)
    if form.source:
        xform = form.wrapped_xform()
    else:
        # This Form doesn't have an xform yet. It is empty.
        # Tell the user this?
        return msgs
    itext = xform.itext_node
    assert(itext.exists())

    # Make language nodes for each language if they don't yet exist
    #
    # Currently operating under the assumption that every xForm has at least
    # one translation element, that each translation element has a text node
    # for each question and that each text node has a value node under it
    template_translation_el = None
    # Get a translation element to be used as a template for new elements
    for lang in app.langs:
        trans_el = itext.find("./{f}translation[@lang='%s']" % lang)
        if trans_el.exists():
            template_translation_el = trans_el
    assert(template_translation_el is not None)
    # Add missing translation elements
    for lang in app.langs:
        trans_el = itext.find("./{f}translation[@lang='%s']" % lang)
        if not trans_el.exists():
            new_trans_el = copy.deepcopy(template_translation_el.xml)
            new_trans_el.set('lang', lang)
            if lang != app.langs[0]:
                # If the language isn't the default language
                new_trans_el.attrib.pop('default')
            else:
                new_trans_el.set('default', '')
            itext.xml.append(new_trans_el)

    for lang in app.langs:
        translation_node = itext.find("./{f}translation[@lang='%s']" % lang)
        assert(translation_node.exists())

        for row in rows:
            question_id = row['label']
            text_node = translation_node.find(
                "./{f}text[@id='%s-label']" % question_id)
            assert(text_node.exists())

            # Add or remove translations
            for trans_type in ['default', 'audio', 'image', 'video']:

                if trans_type == 'default':
                    attributes = None
                    value_node = next(
                        n for n in text_node.findall("./{f}value")
                        if 'form' not in n.attrib
                    )
                else:
                    attributes = {'form': trans_type}
                    value_node = text_node.find(
                        "./{f}value[@form='%s']" % trans_type)

                col_key = get_col_key(trans_type, lang)
                new_translation = row[col_key]
                if not new_translation and col_key not in missing_cols:
                    # If the cell corresponding to the label for this question
                    # in this language is empty, use the default language's
                    # label.
                    # NOTE: This won't help us if we're on the default
                    # language right now
                    new_translation = row[get_col_key(
                        trans_type, app.langs[0]
                    )]

                if new_translation:
                    # create a value node if it doesn't already exist
                    if not value_node.exists():
                        e = etree.Element(
                            "{f}value".format(**namespaces), attributes
                        )
                        text_node.xml.append(e)
                        value_node = WrappedNode(e)
                    # Update the translation
                    value_node.xml.text = new_translation

    save_xform(app, form, etree.tostring(xform.xml, encoding="unicode"))
    return msgs


def update_case_list_translations(sheet, rows, app):
    """
    Modify the translations of a module case list and detail display properties
    given a sheet of translation data. The properties in the sheet must be in
    the exact same order that they appear in the bulk app translation download.
    This function does not save the modified app to the database.

    :param sheet:
    :param rows: The rows of the sheet (we can't get this from the sheet
    because sheet.__iter__ can only be called once)
    :param app:
    :return:  Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    # The list might contain DetailColumn instances in them that have exactly
    # the same attributes (but are in different positions). Therefore we must
    # match sheet rows to DetailColumns by position.
    msgs = []

    module_index = int(sheet.worksheet.title.replace("module", "")) - 1
    module = app.get_module(module_index)

    # It is easier to process the translations if mapping rows are nested under
    # their respective DetailColumns
    condensed_rows = []
    i = 0
    while i < len(rows):
        if rows[i]['case_property'].endswith(" (ID Mapping Text)"):
            # Cut off the id mapping text
            rows[i]['case_property'] = rows[i]['case_property'].split(" ")[0]
            # Construct a list of mapping rows
            mappings = []
            j = 1
            while (i + j < len(rows) and
                    rows[i + j]['case_property'].endswith(" (ID Mapping Value)")):
                # Cut off the id mapping value part
                rows[i + j]['case_property'] = \
                    rows[i + j]['case_property'].split(" ")[0]
                mappings.append(rows[i + j])
                j += 1
            rows[i]['mappings'] = mappings
            condensed_rows.append(rows[i])
            i += j
        else:
            condensed_rows.append(rows[i])
            i += 1

    list_rows = [
        row for row in condensed_rows if row['list_or_detail'] == 'list'
    ]
    detail_rows = [
        row for row in condensed_rows if row['list_or_detail'] == 'detail'
    ]
    short_details = list(module.case_details.short.get_columns())
    long_details = list(module.case_details.long.get_columns())

    # Check length of lists
    for expected_list, received_list, word in [
        (short_details, list_rows, "list"),
        (long_details, detail_rows, "detail")
    ]:
        if len(expected_list) != len(received_list):
            msgs.append((
                messages.error,
                "Expected {0} case {3} properties in sheet {2}, found {1}. "
                "No case list or detail properties for sheet {2} were "
                "updated".format(
                    len(expected_list),
                    len(received_list),
                    sheet.worksheet.title,
                    word
                )
            ))
    if msgs:
        return msgs

    # Update the translations

    for row, detail in \
            zip(list_rows, short_details) + zip(detail_rows, long_details):

        # Check that names match (user is not allowed to change property in the
        # upload). Mismatched names indicate the user probably botched the sheet.
        if row.get('case_property', None) != detail.field:
            msgs.append((
                messages.error,
                'A row in sheet {sheet} has an unexpected value of "{field}" '
                'in the case_property column. Case properties must appear in '
                'the same order as they do in the bulk app translation '
                'download. No translations updated for this row.'.format(
                    sheet=sheet.worksheet.title,
                    field=row.get('case_property', "")
                )
            ))
            continue

        # The logic for updating a mapping and updating a MappingItem and a
        # DetailColumn is almost the same. So, we smush the two together.
        for index, translation_row in enumerate([row] + row.get("mappings", [])):
            ok_to_delete_translations = has_at_least_one_translation(
                translation_row, 'default', app.langs)
            if ok_to_delete_translations:
                for lang in app.langs:
                    translation = translation_row['default_%s' % lang]
                    if index == 0:
                        # For DetailColumns
                        language_dict = detail.header
                    else:
                        # For MappingItems
                        language_dict = detail['enum'][index - 1].value

                    if translation:
                        language_dict[lang] = translation
                    else:
                        language_dict.pop(lang, None)
            else:
                msgs.append((
                    messages.error,
                    "You must provide at least one translation" +
                    " of the case property '%s'" %
                    translation_row['case_property'] + " (ID Mapping Value)"
                    if index != 0 else ""
                ))
    return msgs


def has_at_least_one_translation(row, prefix, langs):
    """
    Returns true if the given row has at least one translation.

    >>> has_at_least_one_translation(
        {'default_en': 'Name', 'case_property': 'name'}, 'default', ['en', 'fra']
    )
    true
    >>> has_at_least_one_translation(
        {'case_property': 'name'}, 'default', ['en', 'fra']
    )
    false

    :param row:
    :param prefix:
    :param langs:
    :return:
    """
    return bool(filter(None, [row[prefix + '_' + l] for l in langs]))


def get_col_key(translation_type, language):
    '''
    Returns the name of the column in the bulk app translation spreadsheet
    given the translation type and language
    :param translation_type: What is being translated, i.e. 'default'
    or 'image'
    :param language:
    :return:
    '''
    return "%s_%s" % (translation_type, language)


def get_translation(id, lang, form, media=None):
    '''
    Returns the label (or media path) for the given question in the given language
    :param id: The identifier for the question, i.e. "question1" or
    "my_multiselect-item6"
    :param lang:
    :param form: XForm object
    :param media: "audio", "video", "image", or None. Returns the appropriate
    media path if provided.
    :return: The label, media path, or "" if no translation is found
    '''
    node_id = "%s-label" % id
    xpath = "./{f}translation[@lang='%s']/{f}text[@id='%s']/{f}value" % \
            (lang, node_id)

    if media:
        xpath += "[@form='%s']" % media
        value_node = form.itext_node.find(xpath)
        return value_node.xml.text if value_node.exists() else ""
    else:
        try:
            value_node = next(
                n for n in form.itext.findall(xpath) if 'form' not in n.attrib
            )
            return value_node.xml.text
        except StopIteration:
            return ""
