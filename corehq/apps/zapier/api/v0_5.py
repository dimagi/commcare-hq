from corehq.apps.api.resources.v0_4 import XFormInstanceResource
from corehq.apps.export.system_properties import MAIN_FORM_TABLE_PROPERTIES


class ZapierXFormInstanceResource(XFormInstanceResource):

    def dehydrate(self, bundle):
        for form_property in MAIN_FORM_TABLE_PROPERTIES:
            if not form_property.is_advanced:
                continue
            element = bundle.data
            for node in form_property.item.path[:-1]:
                element = element.get(node.name)
                if not element:
                    break

            key_to_delete = form_property.item.path[-1].name
            if element and key_to_delete in element:
                del element[key_to_delete]
        return bundle
