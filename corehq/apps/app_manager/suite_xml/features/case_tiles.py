import json
from dataclasses import dataclass, field as dataclass_field
from django.db import models
from django.utils.translation import gettext_lazy as _
from eulxml.xmlmap.core import load_xmlobject_from_string
from memoized import memoized
from pathlib import Path
from typing import List, Dict
from xml.sax.saxutils import escape

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.exceptions import SuiteError
from corehq.apps.app_manager.suite_xml.xml_models import Detail, XPathVariable, TileGroup
from corehq.apps.app_manager.util import (
    module_offers_search,
    module_uses_inline_search,
)


TILE_DIR = Path(__file__).parent.parent / "case_tile_templates"


class CaseTileTemplates(models.TextChoices):
    PERSON_SIMPLE = ("person_simple", _("Person Simple"))
    ONE_ONE_TWO = ("one_one_two", _("Title row, subtitle row, third row with two cells, and map"))
    ONE_TWO_ONE = ("one_two_one", _("Title row, second row with two cells, third row, and map"))
    ONE_TWO_ONE_ONE = ("one_two_one_one", _("Title row, second row with two cells, third and "
                                            "fourth rows, and map"))
    ONE_3X_TWO_4X_ONE_2X = ("one_3X_two_4X_one_2X", _("Three upper rows, four rows with two cells, two lower rows "
                                                    "and map"))
    ONE_TWO_TWO = ("one_two_two", _("Title row, second row with two cells, third row with two cells"))


@dataclass
class CaseTileTemplateConfig:
    slug: str = ''
    filename: str = ''
    has_map: bool = ''
    fields: List[str] = dataclass_field(default_factory=lambda: [])
    grid: Dict[str, Dict[str, int]] = dataclass_field(default_factory=lambda: {})

    @property
    def filepath(self):
        return TILE_DIR / self.filename


@memoized
def case_tile_template_config(template):
    try:
        with open(
            TILE_DIR / (template + '.json'),
            encoding='utf-8'
        ) as f:
            data = json.loads(f.read())
    except FileNotFoundError:
        data = {}
    return CaseTileTemplateConfig(**data)


class CaseTileHelper(object):
    def __init__(self, app, module, detail, detail_id, detail_type, build_profile_id, detail_column_infos,
                 entries_helper):
        self.app = app
        self.module = module
        self.detail = detail
        self.detail_id = detail_id
        self.detail_type = detail_type
        self.cols_by_tile_field = {col.case_tile_field: col for col in self.detail.columns}
        self.build_profile_id = build_profile_id
        self.detail_column_infos = detail_column_infos
        self.entries_helper = entries_helper

    def build_case_tile_detail(self):
        from corehq.apps.app_manager.suite_xml.sections.details import DetailContributor
        """
        Return a Detail node from an apps.app_manager.models.Detail that is
        configured to use case tiles.

        This method does so by injecting the appropriate strings into a template
        string.
        """
        # Get template context
        context = self._get_base_context()
        for template_field in case_tile_template_config(self.detail.case_tile_template).fields:
            column = self._get_matched_detail_column(template_field)
            context[template_field] = self._get_column_context(column)

        # Populate the template
        detail_as_string = self._case_tile_template_string.format(**context)
        detail = load_xmlobject_from_string(detail_as_string, xmlclass=Detail)

        # Case registration
        # The Person simple template already defines a registration action. Since it is used in production
        # it would be a lot of trouble to change it. So if this template is used we will not add another
        # registration action.
        uses_person_simple = self.detail.case_tile_template and \
            self.detail.case_tile_template == CaseTileTemplates.PERSON_SIMPLE.value
        if not uses_person_simple and self.module.case_list_form and self.module.case_list_form.form_id:
            DetailContributor.add_register_action(
                self.app, self.module, detail.actions, self.build_profile_id, self.entries_helper)

        # Add case search action if needed
        if module_offers_search(self.module) and not module_uses_inline_search(self.module):
            if (case_search_action := DetailContributor.get_case_search_action(
                self.module,
                self.build_profile_id,
                self.detail_id
            )) is not None:
                detail.actions.append(case_search_action)

        self._populate_sort_elements_in_detail(detail)
        DetailContributor.add_no_items_text_to_detail(detail, self.app, self.detail_type, self.module)

        if self.module.has_grouped_tiles():
            detail.tile_group = TileGroup(
                function=f"string(./index/{self.detail.case_tile_group.index_identifier})",
                header_rows=self.detail.case_tile_group.header_rows
            )

        return detail

    def _get_matched_detail_column(self, case_tile_field):
        """
        Get the detail column that should populate the given case tile field
        """
        column = self.cols_by_tile_field.get(case_tile_field, None)
        if column is None:
            raise SuiteError(
                'No column was mapped to the "{}" case tile field'.format(
                    case_tile_field
                )
            )
        return column

    def _get_base_context(self):
        """
        Get the basic context variables for interpolation into the
        case tile detail template string
        """
        return {
            "detail_id": id_strings.detail(self.module, self.detail_type),
            "title_text_id": id_strings.detail_title_locale(self.detail_type),
        }

    def _get_column_context(self, column):
        default_lang = self.app.default_language if not self.build_profile_id \
            else self.app.build_profiles[self.build_profile_id].langs[0]
        xpath_function = self._get_xpath_function(column)
        context = {
            "xpath_function": xpath_function,
            "locale_id": id_strings.detail_column_header_locale(
                self.module, self.detail_type, column,
            ),
            # Just using default language for now
            # The right thing to do would be to reference the app_strings.txt I think
            "prefix": escape(
                column.header.get(default_lang, "")
            ),
            "format": column.format
        }

        context['variables'] = ''
        if column.format in ["enum", "conditional-enum", "enum-image"]:
            context["variables"] = self._get_enum_variables(column)
        return context

    def _get_xpath_function(self, column):
        from corehq.apps.app_manager.detail_screen import get_column_generator
        if column.useXpathExpression:
            xpath_function = self._escape_xpath_function(column.field)
        else:
            xpath_function = self._escape_xpath_function(get_column_generator(
                self.app, self.module, self.detail, column).xpath_function)
        return xpath_function

    @staticmethod
    def _escape_xpath_function(xpath_function):
        return escape(xpath_function, {'"': '&quot;'})

    def _get_enum_variables(self, column):
        variables = []
        for i, mapping in enumerate(column.enum):
            variables.append(
                XPathVariable(
                    name=mapping.key_as_variable,
                    locale_id=id_strings.detail_column_enum_variable(
                        self.module, self.detail_type, column, mapping.key_as_variable
                    )
                ).serialize()
            )
        return ''.join([bytes(variable).decode('utf-8') for variable in variables])

    @property
    @memoized
    def _case_tile_template_string(self):
        """
        Return a string suitable for building a case tile detail node
        through `String.format`.
        """
        with open(case_tile_template_config(self.detail.case_tile_template).filepath, encoding='utf-8') as f:
            return f.read()

    def _populate_sort_elements_in_detail(self, detail):
        #  Excludes legacy tile template to preserve behavior of existing apps using this template.
        if self.detail.case_tile_template != CaseTileTemplates.PERSON_SIMPLE.value:
            xpath_to_field = self._get_xpath_mapped_to_field_containing_sort()
            for field in detail.fields:
                populated_xpath_function = self._escape_xpath_function(field.template.text.xpath_function)
                if populated_xpath_function in xpath_to_field:
                    # Adds sort element to the field
                    field.sort_node = xpath_to_field.pop(populated_xpath_function).sort_node

            # detail.fields contains only display properties, not sort-only properties.
            # This adds to detail, hidden fields that contain sort elements.
            for field in xpath_to_field.values():
                detail.fields.append(field)

    def _get_xpath_mapped_to_field_containing_sort(self):
        xpath_to_field = {}
        for column_info in self.detail_column_infos:
            # column_info is an instance of DetailColumnInfo named tuple.
            from corehq.apps.app_manager.detail_screen import get_column_generator
            fields = get_column_generator(
                self.app, self.module, self.detail,
                detail_type=self.detail_type, *column_info
            ).fields
            for field in fields:
                if field.sort_node:
                    xpath_func = self._get_xpath_function(column_info.column)
                    # Handling this for safety, but there likely isn't a use case that would reach this state.
                    if xpath_func in xpath_to_field:
                        field = self._compare_fields_by_order(xpath_to_field[xpath_func], field)
                    xpath_to_field[xpath_func] = field
        return xpath_to_field

    @staticmethod
    def _compare_fields_by_order(initial_field, incoming_field):
        if incoming_field.sort_node.order is None:
            return initial_field
        elif initial_field.sort_node.order is None:
            return incoming_field
        return min(initial_field, incoming_field, key=lambda field: field.sort_node.order)
