from __future__ import absolute_import, unicode_literals

from corehq.apps.app_manager.app_schemas.case_properties import (
    get_parent_type_map,
)
from corehq.apps.app_manager.models import AdvancedModule, Module
from corehq.apps.data_dictionary.util import get_case_property_description_dict
from corehq.apps.reports.formdetails.readable import (
    AppCaseMetadata,
    CaseMetaException,
)


class AppCaseMetadataBuilder(object):
    def __init__(self, domain, app):
        self.domain = domain
        self.app = app
        self.meta = AppCaseMetadata()

    def case_metadata(self):
        self._build_case_relationships()
        self._add_module_contributions()
        return self._get_case_metadata()

    def _get_case_metadata(self):
        descriptions_dict = get_case_property_description_dict(self.domain)

        for module in self.app.get_modules():
            for form in module.get_forms():
                form.update_app_case_meta(self.meta)

        for type_ in self.meta.case_types:
            for prop in type_.properties:
                prop.description = descriptions_dict.get(type_.name, {}).get(prop.name, '')

        return self.meta

    def _build_case_relationships(self):
        case_relationships = get_parent_type_map(self.app)
        for case_type, relationships in case_relationships.items():
            self.meta.get_type(case_type).relationships = relationships

    def _add_module_contributions(self):
        for module in self.app.get_modules():
            if isinstance(module, Module):
                self._add_regular_module_contribution(module)
            elif isinstance(module, AdvancedModule):
                self._add_advanced_module_contribution(module)

    def _add_regular_module_contribution(self, module):
        for column in module.case_details.long.columns:
            try:
                self.meta.add_property_detail('long', module.case_type, module.unique_id, column)
            except CaseMetaException:
                pass
        for column in module.case_details.short.columns:
            try:
                self.meta.add_property_detail('short', module.case_type, module.unique_id, column)
            except CaseMetaException:
                pass

    def _add_advanced_module_contribution(self, module):
        for column in module.case_details.long.columns:
            self.meta.add_property_detail('long', module.case_type, module.unique_id, column)
        for column in module.case_details.short.columns:
            self.meta.add_property_detail('short', module.case_type, module.unique_id, column)
