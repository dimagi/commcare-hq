import json
from dataclasses import dataclass
from django.db import models
from django.utils.translation import gettext_lazy as _
from eulxml.xmlmap.core import load_xmlobject_from_string
from memoized import memoized
from pathlib import Path
from typing import List
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


@dataclass
class CaseTileTemplateConfig:
    slug: str
    filename: str
    fields: List[str]

    @property
    def filepath(self):
        return TILE_DIR / self.filename


@memoized
def case_tile_template_config(template):
    with open(
        TILE_DIR / (template + '.json'),
        encoding='utf-8'
    ) as f:
        data = json.loads(f.read())
    return CaseTileTemplateConfig(**data)


class CaseTileHelper(object):
    def __init__(self, app, module, detail, detail_id, detail_type, build_profile_id):
        self.app = app
        self.module = module
        self.detail = detail
        self.detail_id = detail_id
        self.detail_type = detail_type
        self.cols_by_tile_field = {col.case_tile_field: col for col in self.detail.columns}
        self.build_profile_id = build_profile_id

    def build_case_tile_detail(self):
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

        # Add case search action if needed
        if module_offers_search(self.module) and not module_uses_inline_search(self.module):
            from corehq.apps.app_manager.suite_xml.sections.details import DetailContributor
            detail.actions.append(
                DetailContributor.get_case_search_action(self.module, self.build_profile_id, self.detail_id)
            )

        if self.module.has_grouped_tiles():
            # TODO: check CC version for app
            detail.tile_group = TileGroup(
                function=f"./index/{self.detail.case_tile_group.index_identifier}",
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
        from corehq.apps.app_manager.detail_screen import get_column_generator
        default_lang = self.app.default_language if not self.build_profile_id \
            else self.app.build_profiles[self.build_profile_id].langs[0]
        if column.useXpathExpression:
            xpath_function = escape(column.field, {'"': '&quot;'})
        else:
            xpath_function = escape(get_column_generator(
                self.app, self.module, self.detail, column).xpath_function,
                {'"': '&quot;'})
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
        if column.enum and column.format != "enum" and column.format != "conditional-enum":
            raise SuiteError(
                'Expected case tile field "{}" to be an id mapping with keys {}.'.format(
                    column.case_tile_field,
                    ", ".join(['"{}"'.format(i.key) for i in column.enum])
                )
            )

        context['variables'] = ''
        if column.format == "enum" or column.format == 'conditional-enum':
            context["variables"] = self._get_enum_variables(column)
        return context

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
