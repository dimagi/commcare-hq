from __future__ import absolute_import, unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder

from tastypie.serializers import Serializer

from dimagi.utils.web import get_url_base

from corehq.apps.api.odata.views import (
    ODataCaseMetadataView,
    ODataFormMetadataView,
)
from corehq.apps.export.models import CaseExportInstance, FormExportInstance
from corehq.util.view_utils import absolute_reverse


def _config_to_json(config, documents, table_id):
    if table_id + 1 > len(config.tables):
        return []

    table = config.tables[table_id]
    if not table.selected:
        return []

    data = []
    for row_number, document in enumerate(documents):
        rows = table.get_rows(
            document,
            row_number,
            split_columns=config.split_multiselects,
            transform_dates=config.transform_dates,
            as_json=True,
        )
        data.extend(rows)
    return data


class ODataCaseSerializer(Serializer):

    def to_json(self, data, options=None):
        # Convert bundled objects to JSON
        data['objects'] = [
            bundle.obj for bundle in data['objects']
        ]

        domain = data.pop('domain', None)
        config_id = data.pop('config_id', None)
        api_path = data.pop('api_path', None)
        table_id = data.pop('table_id', None)

        assert all([domain, config_id, api_path, table_id]), [
            domain, config_id, api_path, table_id
        ]

        context_urlname = ODataCaseMetadataView.urlname
        context_url_args = [domain, config_id]
        if table_id > 0:
            context_urlname = ODataCaseMetadataView.urlname_table
            context_url_args.append(table_id)

        data['@odata.context'] = '{}#{}'.format(
            absolute_reverse(context_urlname, args=context_url_args),
            'feed'
        )

        next_link = self.get_next_url(data.pop('meta'), api_path)
        if next_link:
            data['@odata.nextLink'] = next_link

        config = CaseExportInstance.get(config_id)
        data['value'] = self.serialize_cases_using_config(
            data.pop('objects'),
            config,
            table_id
        )
        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)

    @staticmethod
    def get_next_url(meta, api_path):
        next_page = meta['next']
        if next_page:
            return '{}{}{}'.format(get_url_base(), api_path, next_page)

    @staticmethod
    def serialize_cases_using_config(cases, config, table_id):
        return _config_to_json(config, cases, table_id)


class ODataFormSerializer(Serializer):

    def to_json(self, data, options=None):
        # Convert bundled objects to JSON
        data['objects'] = [
            bundle.obj for bundle in data['objects']
        ]

        domain = data.pop('domain', None)
        config_id = data.pop('config_id', None)
        api_path = data.pop('api_path', None)
        table_id = data.pop('table_id', None)

        assert all([domain, config_id, api_path, table_id]), [
            domain, config_id, api_path, table_id
        ]

        context_urlname = ODataFormMetadataView.urlname
        context_url_args = [domain, config_id]
        if table_id > 0:
            context_urlname = ODataFormMetadataView.urlname_table
            context_url_args.append(table_id)

        data['@odata.context'] = '{}#{}'.format(
            absolute_reverse(context_urlname, args=context_url_args),
            'feed'
        )

        next_link = self.get_next_url(data.pop('meta'), api_path)
        if next_link:
            data['@odata.nextLink'] = next_link

        config = FormExportInstance.get(config_id)
        data['value'] = self.serialize_forms_using_config(
            data.pop('objects'),
            config,
            table_id
        )
        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)

    @staticmethod
    def get_next_url(meta, api_path):
        next_page = meta['next']
        if next_page:
            return '{}{}{}'.format(get_url_base(), api_path, next_page)

    @staticmethod
    def serialize_forms_using_config(forms, config, table_id):
        return _config_to_json(config, forms, table_id)
