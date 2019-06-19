# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import itertools
import re
from collections import Counter

from six.moves import zip

from django.contrib import messages
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.app_manager.models import ReportModule
from corehq.apps.translations.app_translations.utils import (
    BulkAppTranslationUpdater,
    get_unicode_dicts,
    get_module_from_sheet_name,
)
from corehq.util.itertools import zip_with_gaps


class BulkAppTranslationModuleUpdater(BulkAppTranslationUpdater):
    def __init__(self, app, sheet_name, unique_id=None, lang=None):
        '''
        :param sheet_name: String like "menu1"
        '''
        super(BulkAppTranslationModuleUpdater, self).__init__(app, lang)
        if unique_id:
            self.module = app.get_module_by_unique_id(unique_id)
        else:
            self.module = get_module_from_sheet_name(self.app, sheet_name)

        # These get populated by _get_condensed_rows
        self.condensed_rows = None
        self.case_list_form_label = None
        self.case_list_menu_item_label = None
        self.tab_headers = None

    def update(self, rows):
        # The list might contain DetailColumn instances in them that have exactly
        # the same attributes (but are in different positions). Therefore we must
        # match sheet rows to DetailColumns by position.
        self.msgs = []

        if isinstance(self.module, ReportModule):
            return self.msgs

        self._get_condensed_rows(rows)

        short_details = list(self.module.case_details.short.get_columns())
        long_details = list(self.module.case_details.long.get_columns())
        list_rows = [row for row in self.condensed_rows if row['list_or_detail'] == 'list']
        detail_rows = [row for row in self.condensed_rows if row['list_or_detail'] == 'detail']

        if (
            len(short_details) == len(list_rows) and
            len(long_details) == len(detail_rows)
        ):
            self._update_details_based_on_position(list_rows, short_details,
                                                   detail_rows, long_details)
        elif toggles.ICDS.enabled(self.app.domain):
            self._partial_upload(list_rows, short_details)
            self._partial_upload(detail_rows, long_details)
        else:
            if len(short_details) != len(list_rows):
                expected_list = short_details
                received_list = list_rows
                list_or_detail = _("case list")
            else:
                expected_list = long_details
                received_list = detail_rows
                list_or_detail = _("case detail")
            message = _(
                'Expected {expected_count} {list_or_detail} properties in '
                'menu {index}, found {actual_count}. No case list or detail '
                'properties for menu {index} were updated.'
            ).format(
                expected_count=len(expected_list),
                actual_count=len(received_list),
                index=self.module.id + 1,
                list_or_detail=list_or_detail
            )
            self.msgs.append((messages.error, message))

        for index, tab in enumerate(self.tab_headers):
            if tab:
                self._update_translation(tab, self.module.case_details.long.tabs[index].header)

        if self.case_list_form_label:
            self._update_translation(self.case_list_form_label, self.module.case_list_form.label)

        if self.case_list_menu_item_label:
            self._update_translation(self.case_list_menu_item_label, self.module.case_list.label)

        return self.msgs

    def _get_condensed_rows(self, rows):
        '''
        Reconfigure the given sheet into objects that are easier to process.
        The major change is to nest mapping and graph config rows under their
        "parent" rows, so that there's one row per case proeprty.

        This function also pulls out case detail tab headers and the case list form label,
        which will be processed separately from the case proeprty rows.

        Populates class attributes condensed_rows, case_list_form_label, case_list_menu_item_label,
        and tab_headers.
        '''
        self.condensed_rows = []
        self.case_list_form_label = None
        self.case_list_menu_item_label = None
        self.tab_headers = [None for i in self.module.case_details.long.tabs]
        index_of_last_enum_in_condensed = -1
        index_of_last_graph_in_condensed = -1
        for i, row in enumerate(get_unicode_dicts(rows)):
            # If it's an enum case property, set index_of_last_enum_in_condensed
            if row['case_property'].endswith(" (ID Mapping Text)"):
                row['id'] = self._remove_description_from_case_property(row)
                self.condensed_rows.append(row)
                index_of_last_enum_in_condensed = len(self.condensed_rows) - 1

            # If it's an enum value, add it to its parent enum property
            elif row['case_property'].endswith(" (ID Mapping Value)"):
                row['id'] = self._remove_description_from_case_property(row)
                parent = self.condensed_rows[index_of_last_enum_in_condensed]
                parent['mappings'] = parent.get('mappings', []) + [row]

            # If it's a graph case property, set index_of_last_graph_in_condensed
            elif row['case_property'].endswith(" (graph)"):
                row['id'] = self._remove_description_from_case_property(row)
                self.condensed_rows.append(row)
                index_of_last_graph_in_condensed = len(self.condensed_rows) - 1

            # If it's a graph configuration item, add it to its parent
            elif row['case_property'].endswith(" (graph config)"):
                row['id'] = self._remove_description_from_case_property(row)
                parent = self.condensed_rows[index_of_last_graph_in_condensed]
                parent['configs'] = parent.get('configs', []) + [row]

            # If it's a graph series configuration item, add it to its parent
            elif row['case_property'].endswith(" (graph series config)"):
                trimmed_property = self._remove_description_from_case_property(row)
                row['id'] = trimmed_property.split(" ")[0]
                row['series_index'] = trimmed_property.split(" ")[1]
                parent = self.condensed_rows[index_of_last_graph_in_condensed]
                parent['series_configs'] = parent.get('series_configs', []) + [row]

            # If it's a graph annotation, add it to its parent
            elif row['case_property'].startswith("graph annotation "):
                row['id'] = int(row['case_property'].split(" ")[-1])
                parent = self.condensed_rows[index_of_last_graph_in_condensed]
                parent['annotations'] = parent.get('annotations', []) + [row]

            # It's the case list registration form label. Don't add it to condensed rows
            elif row['case_property'] == 'case_list_form_label':
                self.case_list_form_label = row

            # It's the case list menu item label. Don't add it to condensed rows
            elif row['case_property'] == 'case_list_menu_item_label':
                self.case_list_menu_item_label = row

            # If it's a tab header, don't add it to condensed rows
            elif re.search(r'^Tab \d+$', row['case_property']):
                index = int(row['case_property'].split(' ')[-1])
                if index < len(self.tab_headers):
                    self.tab_headers[index] = row
                else:
                    message = _("Expected {0} case detail tabs for menu {1} but found row for Tab {2}. No changes "
                                "were made for menu {1}.").format(len(self.tab_headers), self.module.id + 1, index)
                    self.msgs.append((messages.error, message))

            # It's a normal case property
            else:
                row['id'] = row['case_property']
                self.condensed_rows.append(row)

    @classmethod
    def _remove_description_from_case_property(cls, row):
        return re.match('.*(?= \()', row['case_property']).group()

    def _has_at_least_one_translation(self, row, prefix):
        """
        Returns true if the given row has at least one translation.

        Examples, given that self.langs is ['en', 'fra']:
        >>> _has_at_least_one_translation({'default_en': 'Name', 'case_property': 'name'}, 'default')
        True
        >>> _has_at_least_one_translation({'case_property': 'name'}, 'default')
        False
        """
        return any(row.get(prefix + '_' + l) for l in self.langs)

    def _update_translation(self, row, language_dict, require_translation=True):
        if not require_translation or self._has_at_least_one_translation(row, 'default'):
            self.update_translation_dict('default_', language_dict, row)
        else:
            self.msgs.append((
                messages.error,
                _("You must provide at least one translation" +
                  " of the case property '%s'") % row['case_property']
            ))

    def _update_id_mappings(self, rows, detail, langs=None):
        if len(rows) == len(detail.enum) or not toggles.ICDS.enabled(self.app.domain):
            for row, mapping in zip(rows, detail.enum):
                self._update_translation(row, mapping.value)
        else:
            # Not all of the id mappings are described.
            # If we can identify by key, we can proceed.
            mappings_by_prop = {mapping.key: mapping for mapping in detail.enum}
            if len(detail.enum) != len(mappings_by_prop):
                self.msgs.append((
                    messages.error,
                    _("You must provide all ID mappings for property '{}'").format(detail.field)))
            else:
                for row in rows:
                    if row['id'] in mappings_by_prop:
                        self._update_translation(row, mappings_by_prop[row['id']].value)

    def _update_detail(self, row, detail):
        self._update_translation(row, detail.header)
        self._update_id_mappings(row.get('mappings', []), detail)
        for i, graph_annotation_row in enumerate(row.get('annotations', [])):
            self._update_translation(
                graph_annotation_row,
                detail['graph_configuration']['annotations'][i].display_text,
                require_translation=False
            )
        for graph_config_row in row.get('configs', []):
            config_key = graph_config_row['id']
            self._update_translation(
                graph_config_row,
                detail['graph_configuration']['locale_specific_config'][config_key],
                require_translation=False
            )
        for graph_config_row in row.get('series_configs', []):
            config_key = graph_config_row['id']
            series_index = int(graph_config_row['series_index'])
            self._update_translation(
                graph_config_row,
                detail['graph_configuration']['series'][series_index]['locale_specific_config'][config_key],
                require_translation=False
            )

    def _update_details_based_on_position(self, list_rows, short_details, detail_rows, long_details):
        for row, detail in \
                itertools.chain(zip(list_rows, short_details), zip(detail_rows, long_details)):

            # Check that names match (user is not allowed to change property in the
            # upload). Mismatched names indicate the user probably botched the sheet.
            if row.get('id', None) != detail.field:
                message = _('A row for menu {index} has an unexpected case property "{field}". '
                            'Case properties must appear in the same order as they do in the bulk '
                            'app translation download. No translations updated for this row.').format(
                                index=self.module.id + 1,
                                field=row.get('case_property', ""))
                self.msgs.append((messages.error, message))
                continue
            self._update_detail(row, detail)

    def _partial_upload(self, rows, details):
        expected_fields = [detail.field for detail in details]
        received_fields = [row['id'] for row in rows]
        expected_field_counter = Counter(expected_fields)
        received_field_counter = Counter(received_fields)
        for detail, row in zip_with_gaps(details, rows,
                                         lambda detail: detail.field,
                                         lambda row: row['id']):
            field = row['id']
            if (
                received_field_counter[field] > 1 and
                received_field_counter[field] != expected_field_counter[field]
            ):
                message = _(
                    'There is more than one translation for case property '
                    '"{field}" for menu {index}, but some translations are '
                    'missing. Unable to determine which translation(s) to '
                    'use. Skipping this case property.'
                ).format(
                    index=self.module.id + 1,
                    field=row.get('case_property', '')
                )
                self.msgs.append((messages.error, message))
                continue
            self._update_detail(row, detail)
