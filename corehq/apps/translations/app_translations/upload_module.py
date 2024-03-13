import itertools
import re

from django.contrib import messages
from django.utils.translation import gettext as _

from corehq.apps.app_manager.models import ReportModule
from corehq.apps.translations.app_translations.utils import (
    BulkAppTranslationUpdater,
    get_module_from_sheet_name,
    get_unicode_dicts,
)


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
        self.search_label = None
        self.search_again_label = None
        self.title_label = None
        self.description = None
        self.select_text = None
        self.tab_headers = None
        self.no_items_text = None

    def update(self, rows):
        # The list might contain DetailColumn instances in them that have exactly
        # the same attributes (but are in different positions). Therefore we must
        # match sheet rows to DetailColumns by position.
        self.msgs = []

        if isinstance(self.module, ReportModule):
            self._update_report_module_rows(rows)
            return self.msgs

        self._get_condensed_rows(rows)

        short_details_columns = list(self.module.case_details.short.get_columns())
        long_details_columns = list(self.module.case_details.long.get_columns())
        list_rows = [row for row in self.condensed_rows if row['list_or_detail'] == 'list']
        detail_rows = [row for row in self.condensed_rows if row['list_or_detail'] == 'detail']

        if (
            len(short_details_columns) == len(list_rows)
            and len(long_details_columns) == len(detail_rows)
        ):
            self._update_details_based_on_position(list_rows, short_details_columns,
                                                   detail_rows, long_details_columns)
        else:
            if len(short_details_columns) != len(list_rows):
                expected_list = short_details_columns
                received_list = list_rows
                list_or_detail = _("case list")
            else:
                expected_list = long_details_columns
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

        if self.search_label:
            self._update_translation(self.search_label, self.module.search_config.search_label.label)

        if self.search_again_label:
            self._update_translation(self.search_again_label, self.module.search_config.search_again_label.label)

        if self.title_label:
            self._update_translation(self.title_label, self.module.search_config.title_label)

        if self.description:
            self._update_translation(self.description, self.module.search_config.description)

        if self.select_text:
            self._update_translation(self.select_text, self.module.case_details.short.select_text)

        if self.no_items_text:
            self._update_translation(self.no_items_text, self.module.case_details.short.no_items_text)

        self._update_case_search_labels(rows)

        return self.msgs

    def _update_case_search_labels(self, rows):
        properties = self.module.search_config.properties
        displays = [row for row in self.condensed_rows if row['list_or_detail'] == 'case_search_display']
        hints = [row for row in self.condensed_rows if row['list_or_detail'] == 'case_search_hint']
        if len(displays) != len(hints) or len(displays) != len(properties):

            message = _(
                'Expected {expected_count} case_search_display and case_search_hint '
                'properties in  menu {index}, found {actual_label_count} for case_search_display and '
                '{actual_hint_count} for case_search_hint'
                'No Case Search config properties for menu {index} were updated.'
            ).format(
                expected_count=len(properties),
                actual_label_count=len(displays),
                actual_hint_count=len(hints),
                index=self.module.id + 1,
            )
            self.msgs.append((messages.error, message))
        else:
            for display_row, prop in itertools.chain(zip(displays, properties)):
                if display_row.get('case_property') != prop.name:
                    message = _('A display row for menu {index} has an unexpected case search property "{field}". '
                                'Case properties must appear in the same order as they do in the bulk '
                                'app translation download. No translations updated for this row.').format(
                                    index=self.module.id + 1,
                                    field=display_row.get('case_property', ""))
                    self.msgs.append((messages.error, message))
                    continue
                self._update_translation(display_row, prop.label)
            for hint_row, prop in itertools.chain(zip(hints, properties)):
                if hint_row.get('case_property') != prop.name:
                    message = _('A hint row for menu {index} has an unexpected case search property "{field}". '
                                'Case properties must appear in the same order as they do in the bulk '
                                'app translation download. No translations updated for this row.').format(
                                    index=self.module.id + 1,
                                    field=hint_row.get('case_property', ""))
                    self.msgs.append((messages.error, message))
                    continue
                self._update_translation(hint_row, prop.hint)

    def _update_report_module_rows(self, rows):
        new_headers = [None for i in self.module.report_configs]
        new_descriptions = [None for i in self.module.report_configs]
        allow_update = True
        for row in get_unicode_dicts(rows):
            match = re.search(r'^Report (\d+) (Display Text|Description)$', row['case_property'])
            if not match:
                message = _("Found unexpected row \"{0}\" for menu {1}. No changes were made for menu "
                            "{1}.").format(row['case_property'], self.module.id + 1)
                self.msgs.append((messages.error, message))
                allow_update = False
                continue

            index = int(match.group(1))
            try:
                config = self.module.report_configs[index]
            except IndexError:
                message = _("Expected {0} reports for menu {1} but found row for Report {2}. No changes were made "
                            "for menu {1}.").format(len(self.module.report_configs), self.module.id + 1, index)
                self.msgs.append((messages.error, message))
                allow_update = False
                continue

            if match.group(2) == "Display Text":
                new_headers[index] = row
            else:
                if config.use_xpath_description:
                    message = _("Found row for {0}, but this report uses an xpath description, which is not "
                                "localizable. Description not updated.").format(row['case_property'])
                    self.msgs.append((messages.error, message))
                    continue
                new_descriptions[index] = row

        if not allow_update:
            return

        for index, config in enumerate(self.module.report_configs):
            if new_headers[index]:
                self._update_translation(new_headers[index], config.header)
            if new_descriptions[index]:
                self._update_translation(new_descriptions[index], config.localized_description)

    def _get_condensed_rows(self, rows):
        '''
        Reconfigure the given sheet into objects that are easier to process.
        The major change is to nest mapping and graph config rows under their
        "parent" rows, so that there's one row per case proeprty.

        This function also pulls out case detail tab headers and the case list form label,
        which will be processed separately from the case property rows.

        Populates class attributes condensed_rows, case_list_form_label, case_list_menu_item_label,
        case search button labels, and tab_headers.
        '''
        self.condensed_rows = []
        self.case_list_form_label = None
        self.case_list_menu_item_label = None
        self.search_label = None
        self.search_again_label = None
        self.title_label = None
        self.description = None
        self.select_text = None
        self.no_items_text = None
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

            # It's a case search label. Don't add it to condensed rows
            elif row['case_property'] == 'search_label':
                self.search_label = row
            elif row['case_property'] == 'search_again_label':
                self.search_again_label = row
            elif row['case_property'] == 'title_label':
                self.title_label = row
            elif row['case_property'] == 'description':
                self.description = row
            elif row['case_property'] == 'select_text':
                self.select_text = row

            # It's the empty case list text. Don't add it to condensed rows
            elif row['case_property'] == 'no_items_text':
                self.no_items_text = row

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
        return re.match(r'.*(?= \()', row['case_property']).group()

    def _has_at_least_one_translation(self, row, prefix):
        """
        Returns true if the given row has at least one translation.

        Examples, given that self.langs is ['en', 'fra']:
        >>> _has_at_least_one_translation({'default_en': 'Name', 'case_property': 'name'}, 'default')
        True
        >>> _has_at_least_one_translation({'case_property': 'name'}, 'default')
        False
        """
        return any(row.get(prefix + '_' + l) for l in self.langs)  # noqa: E741

    def _update_translation(self, row, language_dict, require_translation=True):
        if not require_translation or self._has_at_least_one_translation(row, 'default'):
            self.update_translation_dict('default_', language_dict, row)
        else:
            self.msgs.append((
                messages.error,
                _("You must provide at least one translation"
                  " of the case property '%s'") % row['case_property']
            ))

    def _update_id_mappings(self, rows, detail, langs=None):
        for row, mapping in zip(rows, detail.enum):
            self._update_translation(row, mapping.value)

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
