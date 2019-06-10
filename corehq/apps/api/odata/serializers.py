from __future__ import absolute_import, unicode_literals
import json

from django.core.serializers.json import DjangoJSONEncoder
from tastypie.serializers import Serializer

from corehq.apps.api.odata.utils import get_case_type_to_properties, get_odata_property_from_export_item
from corehq.apps.api.odata.views import ODataCaseMetadataView, ODataFormMetadataView
from corehq.apps.export.dbaccessors import get_latest_form_export_schema
from corehq.apps.export.models import ExportItem
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
        case_type = data.pop('case_type', None)
        api_path = data.pop('api_path', None)
        assert all([domain, case_type, api_path]), [domain, case_type, api_path]

        data = self.to_simple(data, options)
        data['@odata.context'] = '{}#{}'.format(
            absolute_reverse(ODataCaseMetadataView.urlname, args=[domain]),
            case_type
        )

        next_url = data.pop('meta', {}).get('next')
        if next_url:
            data['@odata.nextLink'] = '{}{}{}'.format(get_url_base(), api_path, next_url)

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


class ODataXFormInstanceSerializer(Serializer):
    """
    A custom serializer that converts form data into an odata-compliant format.
    Must be paired with ODataXFormInstanceResource
    """
    def to_json(self, data, options=None):
        options = options or {}

        domain = data.pop('domain', None)
        app_id = data.pop('app_id', None)
        xmlns = data.pop('xmlns', None)
        api_path = data.pop('api_path', None)
        assert all([domain, app_id, xmlns, api_path]), [domain, app_id, xmlns, api_path]

        data = self.to_simple(data, options)
        data['@odata.context'] = '{}#{}'.format(
            absolute_reverse(ODataFormMetadataView.urlname, args=[domain, app_id]),
            xmlns
        )
        next_url = data.pop('meta', {}).get('next')
        if next_url:
            data['@odata.nextLink'] = '{}{}{}'.format(get_url_base(), api_path, next_url)

        data['value'] = data.pop('objects')

        form_export_schema = get_latest_form_export_schema(
            domain, app_id, xmlns
        )

        if form_export_schema:
            export_items = [
                item for item in form_export_schema.group_schemas[0].items
                if isinstance(item, ExportItem)
            ]

            def _get_odata_value_by_export_item(item, xform_json):
                for path_node in item.path:
                    try:
                        xform_json = xform_json[path_node.name]
                    except KeyError:
                        return None
                return xform_json

            for i, xform_json in enumerate(data['value']):
                data['value'][i] = {
                    get_odata_property_from_export_item(item): _get_odata_value_by_export_item(item, xform_json)
                    for item in export_items
                }
                data['value'][i]['xform_id'] = xform_json['id']

        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)
