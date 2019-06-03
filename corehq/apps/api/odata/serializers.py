from __future__ import absolute_import, unicode_literals
import json

from django.core.serializers.json import DjangoJSONEncoder
from tastypie.serializers import Serializer

from corehq.apps.api.odata.utils import get_case_type_to_properties
from corehq.apps.api.odata.views import ODataCaseMetadataView
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.web import get_url_base


class ODataCommCareCaseSerializer(Serializer):
    """
    A custom serializer that converts case data into an odata-compliant format.
    Must be paired with ODataCommCareCaseResource
    # todo: should maybe be generalized into a mixin paired with the resource to support both cases and forms
    """
    def to_json(self, data, options=None):
        options = options or {}
        domain = data.pop('domain', None)
        if not domain:
            raise Exception('API requires domain to be set! Did you add it in a custom create_response function?')
        case_type = data.pop('case_type', None)
        if not case_type:
            raise Exception(
                'API requires case_type to be set! Did you add it in a custom create_response function?'
            )
        api_path = data.pop('api_path', None)
        if not api_path:
            raise Exception(
                'API requires api_path to be set! Did you add it in a custom create_response function?'
            )
        data = self.to_simple(data, options)
        data['@odata.context'] = '{}#{}'.format(
            absolute_reverse(ODataCaseMetadataView.urlname, args=[domain]),
            case_type
        )

        next_url = data.pop('meta', {}).get('next')
        if next_url:
            data['@odata.nextLink'] = '{}{}{}'.format(get_url_base(), api_path, next_url)
        # move "objects" to "value"
        data['value'] = data.pop('objects')

        # clean properties
        def _clean_property_name(name):
            # for whatever ridiculous reason, at least in Tableau,
            # when these are nested inside an object they can't have underscores in them
            return name.replace('_', '')

        for i, case_json in enumerate(data['value']):
            case_json['properties'] = {_clean_property_name(k): v for k, v in case_json['properties'].items()}

        case_type_to_properties = get_case_type_to_properties(domain)
        properties_to_include = [
            'casename', 'casetype', 'dateopened', 'ownerid', 'backendid'
        ] + case_type_to_properties.get(case_type, [])

        for value in data['value']:
            for remove_property in [
                'id',
                'indexed_on',
                'indices',
                'resource_uri',
            ]:
                value.pop(remove_property)
            properties = value.get('properties')
            for property_name in list(properties):
                if property_name not in properties_to_include:
                    properties.pop(property_name)

        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)
