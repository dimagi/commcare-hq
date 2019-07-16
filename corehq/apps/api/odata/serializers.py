from __future__ import absolute_import, unicode_literals
import json

from django.core.serializers.json import DjangoJSONEncoder

from tastypie.serializers import Serializer

from corehq.apps.api.odata.utils import get_case_type_to_properties, get_odata_property_from_export_item
from corehq.apps.api.odata.views import (
    ODataCaseMetadataView,
    ODataFormMetadataView,
    DeprecatedODataCaseMetadataView,
    DeprecatedODataFormMetadataView,
)
from corehq.apps.export.dbaccessors import get_latest_form_export_schema
from corehq.apps.export.models import CaseExportInstance, ExportItem, FormExportInstance
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.web import get_url_base


class DeprecatedODataCaseSerializer(Serializer):
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
            absolute_reverse(DeprecatedODataCaseMetadataView.urlname, args=[domain]),
            case_type
        )

        next_url = data.pop('meta', {}).get('next')
        if next_url:
            data['@odata.nextLink'] = '{}{}{}'.format(get_url_base(), api_path, next_url)

        data['value'] = data.pop('objects')

        case_json_list = data['value']
        case_properties_to_include = get_properties_to_include(domain, case_type)
        for i, case_json in enumerate(case_json_list):
            update_case_json(case_json, case_properties_to_include)

        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)


def get_properties_to_include(domain, case_type):
    case_type_to_properties = get_case_type_to_properties(domain)
    return [
        'case_name', 'case_type', 'date_opened', 'owner_id', 'backend_id'
    ] + case_type_to_properties.get(case_type, [])


def update_case_json(case_json, case_properties_to_include):
    for remove_property in [
        'id',
        'indexed_on',
        'indices',
        'resource_uri',
    ]:
        case_json.pop(remove_property)
    case_properties = case_json.pop('properties')
    case_json.update({
        property_name: case_properties.get(property_name, None)
        for property_name in case_properties_to_include
    })


class DeprecatedODataFormSerializer(Serializer):
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
            absolute_reverse(DeprecatedODataFormMetadataView.urlname, args=[domain, app_id]),
            xmlns
        )
        next_url = data.pop('meta', {}).get('next')
        if next_url:
            data['@odata.nextLink'] = '{}{}{}'.format(get_url_base(), api_path, next_url)

        data['value'] = data.pop('objects')

        form_export_schema = get_latest_form_export_schema(
            domain, app_id, 'http://openrosa.org/formdesigner/' + xmlns
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


class ODataCaseSerializer(Serializer):

    def to_json(self, data, options=None):
        # Convert bundled objects to JSON
        data['objects'] = [
            bundle.obj for bundle in data['objects']
        ]

        domain = data.pop('domain', None)
        config_id = data.pop('config_id', None)
        api_path = data.pop('api_path', None)
        assert all([domain, config_id, api_path]), [domain, config_id, api_path]

        data['@odata.context'] = '{}#{}'.format(
            absolute_reverse(ODataCaseMetadataView.urlname, args=[domain]),
            config_id
        )

        next_link = self.get_next_url(data.pop('meta'), api_path)
        if next_link:
            data['@odata.nextLink'] = next_link

        config = CaseExportInstance.get(config_id)
        data['value'] = self.serialize_cases_using_config(data.pop('objects'), config)

        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)

    @staticmethod
    def get_next_url(meta, api_path):
        next_page = meta['next']
        if next_page:
            return '{}{}{}'.format(get_url_base(), api_path, next_page)

    @staticmethod
    def serialize_cases_using_config(cases, config):
        table = config.tables[0]
        return [
            {
                col.label: col.get_value(
                    config.domain,
                    case_data.get('case_id', None),
                    case_data,
                    [],
                    split_column=config.split_multiselects,
                    transform_dates=config.transform_dates,
                )
                for col in table.selected_columns
            }
            for case_data in cases
        ]


class ODataFormSerializer(Serializer):

    def to_json(self, data, options=None):
        # Convert bundled objects to JSON
        data['objects'] = [
            bundle.obj for bundle in data['objects']
        ]

        domain = data.pop('domain', None)
        config_id = data.pop('config_id', None)
        api_path = data.pop('api_path', None)
        assert all([domain, config_id, api_path]), [domain, config_id, api_path]

        data['@odata.context'] = '{}#{}'.format(
            absolute_reverse(ODataFormMetadataView.urlname, args=[domain]),
            config_id
        )

        next_link = self.get_next_url(data.pop('meta'), api_path)
        if next_link:
            data['@odata.nextLink'] = next_link

        config = FormExportInstance.get(config_id)
        data['value'] = self.serialize_forms_using_config(data.pop('objects'), config)

        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)

    @staticmethod
    def get_next_url(meta, api_path):
        next_page = meta['next']
        if next_page:
            return '{}{}{}'.format(get_url_base(), api_path, next_page)

    @staticmethod
    def serialize_forms_using_config(forms, config):
        table = config.tables[0]
        return [
            {
                col.label: col.get_value(
                    config.domain,
                    form_data.get('_id', None),
                    form_data,
                    [],
                    split_column=config.split_multiselects,
                    transform_dates=config.transform_dates,
                )
                for col in table.selected_columns
            }
            for form_data in forms
        ]
