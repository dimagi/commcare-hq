from __future__ import absolute_import, unicode_literals
import json

from django.core.serializers.json import DjangoJSONEncoder
from tastypie.serializers import Serializer

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
        domain = data.get('domain')
        if not domain:
            raise Exception('API requires domain to be set! Did you add it in a custom create_response function?')
        resource_name = data.get('resource_name')
        if not resource_name:
            raise Exception(
                'API requires resource_name to be set! Did you add it in a custom create_response function?'
            )
        api_path = data.pop('api_path', None)
        if not api_path:
            raise Exception(
                'API requires api_path to be set! Did you add it in a custom create_response function?'
            )
        data = self.to_simple(data, options)
        data['@odata.context'] = '{}#{}'.format(absolute_reverse('odata_meta', args=[domain]), resource_name)

        next_url = data.get('meta', {}).get('next')
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

        data.pop('domain')
        data.pop('meta')
        data.pop('resource_name')

        for value in data['value']:
            value.pop('date_closed')

        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)
