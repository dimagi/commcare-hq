from __future__ import absolute_import, unicode_literals

from corehq.apps.app_manager.app_schemas.case_properties import (
    get_parent_type_map,
)
from corehq.apps.data_dictionary.util import get_case_property_description_dict
from corehq.apps.reports.formdetails.readable import AppCaseMetadata


class AppCaseMetadataBuilder(object):
    def __init__(self, domain, app):
        self.domain = domain
        self.app = app

    def case_metadata(self):
        return self._get_case_metadata()

    def _get_case_metadata(self):
        case_relationships = get_parent_type_map(self.app)
        meta = AppCaseMetadata()
        descriptions_dict = get_case_property_description_dict(self.domain)

        for case_type, relationships in case_relationships.items():
            type_meta = meta.get_type(case_type)
            type_meta.relationships = relationships

        for module in self.app.get_modules():
            module.update_app_case_meta(meta)
            for form in module.get_forms():
                form.update_app_case_meta(meta)

        for type_ in meta.case_types:
            for prop in type_.properties:
                prop.description = descriptions_dict.get(type_.name, {}).get(prop.name, '')

        return meta
