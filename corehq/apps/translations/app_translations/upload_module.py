# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import itertools
import re
from six.moves import zip

from django.contrib import messages
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.app_manager.models import ReportModule
from corehq.apps.translations.app_translations.utils import get_unicode_dicts, update_translation_dict



def update_app_from_module_sheet(app, rows, identifier):
    """
    Modify the translations of a module case list and detail display properties
    given a sheet of translation data. The properties in the sheet must be in
    the exact same order that they appear in the bulk app translation download.
    This function does not save the modified app to the database.

    :param app:
    :param rows: Iterable of rows from a WorksheetJSONReader
    :return:  Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    # The list might contain DetailColumn instances in them that have exactly
    # the same attributes (but are in different positions). Therefore we must
    # match sheet rows to DetailColumns by position.
    msgs = []

    module = _get_module_from_sheet_name(app, identifier)
    if isinstance(module, ReportModule):
        return msgs

    (condensed_rows, detail_tab_headers, case_list_form_label) = _get_condensed_rows(module, rows)

    (errors, partial_upload) = _check_for_detail_length_errors(module, condensed_rows)
    if errors:
        return [(messages.error, e) for e in errors]

    # Update the translations
    def _update_translation(row, language_dict, require_translation=True):
        ok_to_delete_translations = (
            not require_translation or _has_at_least_one_translation(
                    row, 'default', app.langs
            ))
        if ok_to_delete_translations:
            update_translation_dict('default_', language_dict, row, app.langs)
        else:
            msgs.append((
                messages.error,
                _("You must provide at least one translation" +
                  " of the case property '%s'") % row['case_property']
            ))

    def _update_id_mappings(rows, detail):
        if len(rows) == len(detail.enum) or not toggles.ICDS.enabled(app.domain):
            for row, mapping in zip(rows, detail.enum):
                _update_translation(row, mapping.value)
        else:
            # Not all of the id mappings are described.
            # If we can identify by key, we can proceed.
            mappings_by_prop = {mapping.key: mapping for mapping in detail.enum}
            if len(detail.enum) != len(mappings_by_prop):
                msgs.append((messages.error,
                             _("You must provide all ID mappings for property '{}'")
                             .format(detail.field)))
            else:
                for row in rows:
                    if row['id'] in mappings_by_prop:
                        _update_translation(row, mappings_by_prop[row['id']].value)

    def _update_detail(row, detail):
        # Update the translations for the row and all its child rows
        _update_translation(row, detail.header)
        _update_id_mappings(row.get('mappings', []), detail)
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
        for graph_config_row in row.get('series_configs', []):
            config_key = graph_config_row['id']
            series_index = int(graph_config_row['series_index'])
            _update_translation(
                graph_config_row,
                detail['graph_configuration']['series'][series_index]['locale_specific_config'][config_key],
                False
            )

    def _update_details_based_on_position(list_rows, short_details, detail_rows, long_details):
        for row, detail in \
                itertools.chain(zip(list_rows, short_details), zip(detail_rows, long_details)):

            # Check that names match (user is not allowed to change property in the
            # upload). Mismatched names indicate the user probably botched the sheet.
            if row.get('id', None) != detail.field:
                message = _('A row for menu {index} has an unexpected case property "{field}"'
                            'Case properties must appear in the same order as they do in the bulk '
                            'app translation download. No translations updated for this row.').format(
                                index=module.id + 1,
                                field=row.get('case_property', ""))
                msgs.append((messages.error, message))
                continue
            _update_detail(row, detail)

    def _partial_upload(rows, details):
        rows_by_property = {row['id']: row for row in rows}
        for detail in details:
            if rows_by_property.get(detail.field):
                _update_detail(rows_by_property.get(detail.field), detail)

    short_details = list(module.case_details.short.get_columns())
    long_details = list(module.case_details.long.get_columns())
    list_rows = [row for row in condensed_rows if row['list_or_detail'] == 'list']
    detail_rows = [row for row in condensed_rows if row['list_or_detail'] == 'detail']
    if partial_upload:
        _partial_upload(list_rows, short_details)
        _partial_upload(detail_rows, long_details)
    else:
        _update_details_based_on_position(list_rows, short_details, detail_rows, long_details)

    for index, tab in enumerate(detail_tab_headers):
        if tab:
            _update_translation(tab, module.case_details.long.tabs[index].header)
    if case_list_form_label:
        _update_translation(case_list_form_label, module.case_list_form.label)

    return msgs


def _get_condensed_rows(module, rows):
    '''
    Reconfigure the given sheet into objects that are easier to process.
    The major change is to nest mapping and graph config rows under their
    "parent" rows, so that there's one row per case proeprty.

    This function also pulls out case detail tab headers and the case list form label,
    which will be processed separately from the case proeprty rows.

    Returns a three-item tuple: case property rows, tab header rows, case list form label
    '''
    condensed_rows = []
    case_list_form_label = None
    detail_tab_headers = [None for i in module.case_details.long.tabs]
    index_of_last_enum_in_condensed = -1
    index_of_last_graph_in_condensed = -1
    for i, row in enumerate(get_unicode_dicts(rows)):
        # If it's an enum case property, set index_of_last_enum_in_condensed
        if row['case_property'].endswith(" (ID Mapping Text)"):
            row['id'] = _remove_description_from_case_property(row)
            condensed_rows.append(row)
            index_of_last_enum_in_condensed = len(condensed_rows) - 1

        # If it's an enum value, add it to its parent enum property
        elif row['case_property'].endswith(" (ID Mapping Value)"):
            row['id'] = _remove_description_from_case_property(row)
            parent = condensed_rows[index_of_last_enum_in_condensed]
            parent['mappings'] = parent.get('mappings', []) + [row]

        # If it's a graph case property, set index_of_last_graph_in_condensed
        elif row['case_property'].endswith(" (graph)"):
            row['id'] = _remove_description_from_case_property(row)
            condensed_rows.append(row)
            index_of_last_graph_in_condensed = len(condensed_rows) - 1

        # If it's a graph configuration item, add it to its parent
        elif row['case_property'].endswith(" (graph config)"):
            row['id'] = _remove_description_from_case_property(row)
            parent = condensed_rows[index_of_last_graph_in_condensed]
            parent['configs'] = parent.get('configs', []) + [row]

        # If it's a graph series configuration item, add it to its parent
        elif row['case_property'].endswith(" (graph series config)"):
            trimmed_property = _remove_description_from_case_property(row)
            row['id'] = trimmed_property.split(" ")[0]
            row['series_index'] = trimmed_property.split(" ")[1]
            parent = condensed_rows[index_of_last_graph_in_condensed]
            parent['series_configs'] = parent.get('series_configs', []) + [row]

        # If it's a graph annotation, add it to its parent
        elif row['case_property'].startswith("graph annotation "):
            row['id'] = int(row['case_property'].split(" ")[-1])
            parent = condensed_rows[index_of_last_graph_in_condensed]
            parent['annotations'] = parent.get('annotations', []) + [row]

        # It's a case list registration form label. Don't add it to condensed rows
        elif row['case_property'] == 'case_list_form_label':
            case_list_form_label = row

        # If it's a tab header, don't add it to condensed rows
        elif re.search(r'^Tab \d+$', row['case_property']):
            index = int(row['case_property'].split(' ')[-1])
            if index < len(detail_tab_headers):
                detail_tab_headers[index] = row
            else:
                message = _("Expected {0} case detail tabs for menu {1} but found row for Tab {2}. No changes "
                            "were made for menu {1}.").format(len(detail_tab_headers), module.id + 1, index)
                msgs.append((messages.error, message))

        # It's a normal case property
        else:
            row['id'] = row['case_property']
            condensed_rows.append(row)

    return (condensed_rows, detail_tab_headers, case_list_form_label)


def _remove_description_from_case_property(row):
    return re.match('.*(?= \()', row['case_property']).group()


def _check_for_detail_length_errors(module, condensed_rows):
    errors = []

    list_rows = [row for row in condensed_rows if row['list_or_detail'] == 'list']
    detail_rows = [row for row in condensed_rows if row['list_or_detail'] == 'detail']
    short_details = list(module.case_details.short.get_columns())
    long_details = list(module.case_details.long.get_columns())
    partial_upload = False

    for expected_list, received_list, list_or_detail in [
        (short_details, list_rows, _("case list")),
        (long_details, detail_rows, _("case detail")),
    ]:
        if len(expected_list) != len(received_list):
            # if a field is not referenced twice in a case list or detail, then
            # we can perform a partial upload using field (case property) as a key
            number_fields = len({detail.field for detail in expected_list})
            if number_fields == len(expected_list) and toggles.ICDS.enabled(module.get_app().domain):
                partial_upload = True
                continue
            errors.append(_("Expected {expected_count} {list_or_detail} properties in menu {index}, found "
                "{actual_count}. No case list or detail properties for menu {index} were updated").format(
                    expected_count=len(expected_list),
                    actual_count=len(received_list),
                    index=module.id + 1,
                    list_or_detail=list_or_detail,
                )
            )

    return (errors, partial_upload)


def _get_module_from_sheet_name(app, identifier):
    module_index = int(identifier.replace("module", "").replace("menu", "")) - 1
    return app.get_module(module_index)


def _has_at_least_one_translation(row, prefix, langs):
    """
    Returns true if the given row has at least one translation.

    >> has_at_least_one_translation(
        {'default_en': 'Name', 'case_property': 'name'}, 'default', ['en', 'fra']
    )
    true
    >> has_at_least_one_translation(
        {'case_property': 'name'}, 'default', ['en', 'fra']
    )
    false

    :param row:
    :param prefix:
    :param langs:
    :return:
    """
    return any(row.get(prefix + '_' + l) for l in langs)
