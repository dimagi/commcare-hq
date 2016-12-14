import json

from corehq.apps.api.resources.v0_4 import XFormInstanceResource
from corehq.apps.api.serializers import XFormInstanceSerializer
from corehq.apps.export.system_properties import MAIN_FORM_TABLE_PROPERTIES


class ZapierXFormInstanceSerializer(XFormInstanceSerializer):

    def to_json(self, data, options=None):
        form_json = json.loads(super(ZapierXFormInstanceSerializer, self).to_json(data, options))
        forms = form_json['objects']

        for form in forms:
            for form_property in MAIN_FORM_TABLE_PROPERTIES:
                if not form_property.is_advanced:
                    continue
                element = form
                for node in form_property.item.path[:-1]:
                    element = element.get(node.name)
                    if not element:
                        break

                key_to_delete = form_property.item.path[-1].name
                if element and key_to_delete in element:
                    del element[key_to_delete]

        return json.dumps(form_json)


class ZapierXFormInstanceResource(XFormInstanceResource):

    class Meta(XFormInstanceResource.Meta):
        serializer = ZapierXFormInstanceSerializer(formats=['json'])
