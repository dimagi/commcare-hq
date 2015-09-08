from collections import OrderedDict
from django.utils.html import escape
from lxml import etree
import copy
import re
from lxml.etree import XMLSyntaxError, Element
from openpyxl.utils.exceptions import InvalidFileException

from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    ModuleNotFoundException,
    XFormException)
from corehq.apps.app_manager.models import ReportModule
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import namespaces, WrappedNode, ItextValue, ItextOutput
from corehq.util.spreadsheets.excel import HeaderValueError, WorkbookJSONReader

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

    def none_or_unicode(val):
        return unicode(val) if val is not None else val

    msgs = []

    headers = expected_bulk_app_sheet_headers(app)
    expected_sheets = {h[0]: h[1] for h in headers}
    processed_sheets = set()

    try:
        workbook = WorkbookJSONReader(f)
    except (HeaderValueError, InvalidFileException) as e:
        msgs.append(
            (messages.error, _(
                "App Translation Failed! "
                "Please make sure you are using a valid Excel 2007 or later (.xlsx) file. "
                "Error details: {}."
            ).format(e))
        )
        return msgs

    for sheet in workbook.worksheets:
        # sheet.__iter__ can only be called once, so cache the result
        rows = [row for row in sheet]
        # Convert every key and value to a string
        for i in xrange(len(rows)):
            rows[i] = {unicode(k): none_or_unicode(v) for k, v in rows[i].iteritems()}

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
                    'Skipping sheet "%s", could not find label column' %
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


def make_modules_and_forms_row(row_type, sheet_name, languages, case_labels,
                               media_image, media_audio, unique_id):
    """
    assemble the various pieces of data that make up a row in the
    "Modules_and_forms" sheet into a single row (a flat tuple).

    This function is meant as the single point of truth for the
    column ordering of Modules_and_forms

    """
    assert row_type is not None
    assert sheet_name is not None
    assert isinstance(languages, list)
    assert isinstance(case_labels, list)
    assert isinstance(media_image, list)
    assert isinstance(media_audio, list)
    assert isinstance(unique_id, basestring)

    return [item if item is not None else ""
            for item in ([row_type, sheet_name] + languages + case_labels
                         + media_image + media_audio + [unique_id])]


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
    headers.append([
        "Modules_and_forms",
        make_modules_and_forms_row(
            row_type='Type',
            sheet_name='sheet_name',
            languages=languages_list,
            case_labels=['label_for_cases_%s' % l for l in app.langs],
            media_image=['icon_filepath_%s' % l for l in app.langs],
            media_audio=['audio_filepath_%s' % l for l in app.langs],
            unique_id='unique_id',
        )
    ])

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


def expected_bulk_app_sheet_rows(app):

    # keys are the names of sheets, values are lists of tuples representing rows
    rows = {"Modules_and_forms": []}

    for mod_index, module in enumerate(app.get_modules()):
        # This is duplicated logic from expected_bulk_app_sheet_headers,
        # which I don't love.
        module_string = "module" + str(mod_index + 1)

        # Add module to the first sheet
        row_data = make_modules_and_forms_row(
            row_type="Module",
            sheet_name=module_string,
            languages=[module.name.get(lang) for lang in app.langs],
            case_labels=[module.case_label.get(lang) for lang in app.langs],
            media_image=[module.icon_by_language(lang) for lang in app.langs],
            media_audio=[module.audio_by_language(lang) for lang in app.langs],
            unique_id=module.unique_id,
        )
        rows["Modules_and_forms"].append(row_data)

        # Populate module sheet
        rows[module_string] = []
        if not isinstance(module, ReportModule):
            for list_or_detail, case_properties in [
                ("list", module.case_details.short.get_columns()),
                ("detail", module.case_details.long.get_columns())
            ]:
                for detail in case_properties:

                    field_name = detail.field
                    if detail.format == "enum":
                        field_name += " (ID Mapping Text)"
                    elif detail.format == "graph":
                        field_name += " (graph)"

                    # Add a row for this case detail
                    rows[module_string].append(
                        (field_name, list_or_detail) +
                        tuple(detail.header.get(lang, "") for lang in app.langs)
                    )

                    # Add a row for any mapping pairs
                    if detail.format == "enum":
                        for mapping in detail.enum:
                            rows[module_string].append(
                                (
                                    mapping.key + " (ID Mapping Value)",
                                    list_or_detail
                                ) + tuple(
                                    mapping.value.get(lang, "")
                                    for lang in app.langs
                                )
                            )

                    # Add rows for graph configuration
                    if detail.format == "graph":
                        for key, val in detail.graph_configuration.locale_specific_config.iteritems():
                            rows[module_string].append(
                                (
                                    key + " (graph config)",
                                    list_or_detail
                                ) + tuple(val.get(lang, "") for lang in app.langs)
                            )
                        for i, annotation in enumerate(detail.graph_configuration.annotations):
                            rows[module_string].append(
                                (
                                    "graph annotation {}".format(i + 1),
                                    list_or_detail
                                ) + tuple(
                                    annotation.display_text.get(lang, "")
                                    for lang in app.langs
                                )
                            )

            for form_index, form in enumerate(module.get_forms()):
                form_string = module_string + "_form" + str(form_index + 1)
                xform = form.wrapped_xform()

                # Add row for this form to the first sheet
                # This next line is same logic as above :(
                first_sheet_row = make_modules_and_forms_row(
                    row_type="Form",
                    sheet_name=form_string,
                    languages=[form.name.get(lang) for lang in app.langs],
                    # leave all
                    case_labels=[None] * len(app.langs),
                    media_image=[form.icon_by_language(lang) for lang in app.langs],
                    media_audio=[form.audio_by_language(lang) for lang in app.langs],
                    unique_id=form.unique_id
                )

                # Add form to the first street
                rows["Modules_and_forms"].append(first_sheet_row)

                # Populate form sheet
                rows[form_string] = []

                itext_items = OrderedDict()
                try:
                    nodes = xform.itext_node.findall("./{f}translation")
                except XFormException:
                    nodes = []

                for translation_node in nodes:
                    lang = translation_node.attrib['lang']
                    for text_node in translation_node.findall("./{f}text"):
                        text_id = text_node.attrib['id']
                        itext_items[text_id] = itext_items.get(text_id, {})

                        for value_node in text_node.findall("./{f}value"):
                            value_form = value_node.attrib.get("form", "default")
                            value = ''
                            for part in ItextValue.from_node(value_node).parts:
                                if isinstance(part, ItextOutput):
                                    value += "<output value=\"" + part.ref + "\"/>"
                                else:
                                    value += escape(part)
                            itext_items[text_id][(lang, value_form)] = value

                for text_id, values in itext_items.iteritems():
                    row = [text_id]
                    for value_form in ["default", "audio", "image", "video"]:
                        # Get the fallback value for this form
                        fallback = ""
                        for lang in app.langs:
                            fallback = values.get((lang, value_form), fallback)
                            if fallback:
                                break
                        # Populate the row
                        for lang in app.langs:
                            row.append(values.get((lang, value_form), fallback))
                    # Don't add empty rows:
                    if any(row[1:]):
                        rows[form_string].append(row)
    return rows


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

        for lang in app.langs:
            translation = row['default_%s' % lang]
            if translation:
                document.name[lang] = translation
            else:
                if lang in document.name:
                    del document.name[lang]

        if (has_at_least_one_translation(row, 'label_for_cases', app.langs)
                and hasattr(document, 'case_label')):
            for lang in app.langs:
                translation = row['label_for_cases_%s' % lang]
                if translation:
                    document.case_label[lang] = translation
                else:
                    if lang in document.case_label:
                        del document.case_label[lang]

        for lang in app.langs:
            document.set_icon(lang, row.get('icon_filepath_%s' % lang, ''))
            document.set_audio(lang, row.get('audio_filepath_%s' % lang, ''))

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

    try:
        itext = xform.itext_node
    except XFormException:
        return msgs

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
                new_trans_el.attrib.pop('default', None)
            else:
                new_trans_el.set('default', '')
            itext.xml.append(new_trans_el)

    # Update the translations
    for lang in app.langs:
        translation_node = itext.find("./{f}translation[@lang='%s']" % lang)
        assert(translation_node.exists())

        for row in rows:
            label_id = row['label']
            text_node = translation_node.find("./{f}text[@id='%s']" % label_id)
            if not text_node.exists():
                msgs.append((
                    messages.warning,
                    "Unrecognized translation label {0} in sheet {1}. That row"
                    " has been skipped". format(label_id, sheet.worksheet.title)
                ))
                continue

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
                        "./{f}value[@form='%s']" % trans_type
                    )

                try:
                    col_key = get_col_key(trans_type, lang)
                    new_translation = row[col_key]
                except KeyError:
                    # error has already been logged as unrecoginzed column
                    continue
                if not new_translation and col_key not in missing_cols:
                    # If the cell corresponding to the label for this question
                    # in this language is empty, fall back to another language
                    for l in app.langs:
                        key = get_col_key(trans_type, l)
                        if key in missing_cols:
                            continue
                        fallback = row[key]
                        if fallback:
                            new_translation = fallback
                            break

                if new_translation:
                    # Create the node if it does not already exist
                    if not value_node.exists():
                        e = etree.Element(
                            "{f}value".format(**namespaces), attributes
                        )
                        text_node.xml.append(e)
                        value_node = WrappedNode(e)
                    # Update the translation
                    value_node.xml.tail = ''
                    for node in value_node.findall("./*"):
                        node.xml.getparent().remove(node.xml)
                    escaped_trans = escape_output_value(new_translation)
                    value_node.xml.text = escaped_trans.text
                    for n in escaped_trans.getchildren():
                        value_node.xml.append(n)
                else:
                    # Remove the node if it already exists
                    if value_node.exists():
                        value_node.xml.getparent().remove(value_node.xml)

    save_xform(app, form, etree.tostring(xform.xml, encoding="unicode"))
    return msgs


def escape_output_value(value):
    try:
        return etree.fromstring(u"<value>{}</value>".format(
            re.sub("(?<!/)>", "&gt;", re.sub("<(\s*)(?!output)", "&lt;\\1", value))
        ))
    except XMLSyntaxError:
        # if something went horribly wrong just don't bother with escaping
        element = Element('value')
        element.text = value
        return element


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

    # It is easier to process the translations if mapping and graph config
    # rows are nested under their respective DetailColumns.

    condensed_rows = []
    index_of_last_enum_in_condensed = -1
    index_of_last_graph_in_condensed = -1
    for i, row in enumerate(rows):
        # If it's an enum case property, set index_of_last_enum_in_condensed
        if row['case_property'].endswith(" (ID Mapping Text)"):
            row['id'] = row['case_property'].split(" ")[0]
            condensed_rows.append(row)
            index_of_last_enum_in_condensed = len(condensed_rows) - 1

        # If it's an enum value, add it to it's parent enum property
        elif row['case_property'].endswith(" (ID Mapping Value)"):
            row['id'] = row['case_property'].split(" ")[0]
            parent = condensed_rows[index_of_last_enum_in_condensed]
            parent['mappings'] = parent.get('mappings', []) + [row]

        # If it's a graph case property, set index_of_last_graph_in_condensed
        elif row['case_property'].endswith(" (graph)"):
            row['id'] = row['case_property'].split(" ")[0]
            condensed_rows.append(row)
            index_of_last_graph_in_condensed = len(condensed_rows) - 1

        # If it's a graph configuration item, add it to its parent
        elif row['case_property'].endswith(" (graph config)"):
            row['id'] = row['case_property'].split(" ")[0]
            parent = condensed_rows[index_of_last_graph_in_condensed]
            parent['configs'] = parent.get('configs', []) + [row]

        # If it's a graph annotation, add it to its parent
        elif row['case_property'].startswith("graph annotation "):
            row['id'] = int(row['case_property'].split(" ")[-1])
            parent = condensed_rows[index_of_last_graph_in_condensed]
            parent['annotations'] = parent.get('annotations', []) + [row]

        # It's a normal case property
        else:
            row['id'] = row['case_property']
            condensed_rows.append(row)

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
        if row.get('id', None) != detail.field:
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

        def _update_translation(row, language_dict, require_translation=True):
            ok_to_delete_translations = (
                not require_translation or has_at_least_one_translation(
                    row, 'default', app.langs
                ))
            if ok_to_delete_translations:
                for lang in app.langs:
                    translation = row['default_%s' % lang]
                    if translation:
                        language_dict[lang] = translation
                    else:
                        language_dict.pop(lang, None)
            else:
                msgs.append((
                    messages.error,
                    "You must provide at least one translation" +
                    " of the case property '%s'" % row['case_property']
                ))

        # Update the translations for the row and all its child rows
        _update_translation(row, detail.header)
        for i, enum_value_row in enumerate(row.get('mappings', [])):
            _update_translation(enum_value_row, detail['enum'][i].value)
        for i, graph_annotation_row in enumerate(row.get('annotations', [])):
            _update_translation(
                graph_annotation_row,
                detail['graph_configuration']['annotations'][i].display_text,
                False
            )
        for graph_config_row in row.get('configs', []):
            config_key = graph_config_row['id']
            _update_translation(
                graph_config_row,
                detail['graph_configuration']['locale_specific_config'][config_key],
                False
            )

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
