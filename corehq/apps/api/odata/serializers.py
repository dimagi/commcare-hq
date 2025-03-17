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
from corehq.apps.api.odata.utils import format_odata_error


class ODataBaseSerializer(Serializer):

    metadata_url = None
    table_metadata_url = None
    offset = 0

    def get_config(self, config_id):
        raise NotImplementedError("implement get_config")

    def to_json(self, data, options=None):
        # get current object offset for use in row number
        self.offset = data.get('meta', {}).get('offset', 0)

        if 'objects' not in data.keys():
            return json.dumps(format_odata_error("404",
            "This OData feed does not exist"),
            cls=DjangoJSONEncoder)

        # Convert bundled objects to JSON
        data['objects'] = [
            bundle.obj for bundle in data['objects']
        ]

        domain = data.pop('domain', None)
        config_id = data.pop('config_id', None)
        api_path = data.pop('api_path', None)
        api_version = data.pop('api_version', None)
        table_id = data.pop('table_id', None)

        assert all([domain, config_id, api_path, api_version]), \
            [domain, config_id, api_path, api_version]

        context_urlname = self.metadata_url
        context_url_args = [domain, api_version, config_id]
        if table_id > 0:
            context_urlname = self.table_metadata_url
            context_url_args.append(table_id)

        data['@odata.context'] = '{}#{}'.format(
            absolute_reverse(context_urlname, args=context_url_args),
            'feed'
        )

        next_link = self.get_next_url(data.pop('meta'), api_path)
        if next_link:
            data['@odata.nextLink'] = next_link

        config = self.get_config(config_id)
        data['value'] = self.serialize_documents_using_config(
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
    def serialize_documents_using_config(documents, config, table_id):
        if table_id + 1 > len(config.tables):
            return []

        table = config.tables[table_id]
        if not table.selected:
            return []

        data = []
        for row_number, document in enumerate(documents):
            rows = table.get_rows(
                document,
                document.get('_id'),  # needed because of pagination
                split_columns=config.split_multiselects,
                transform_dates=config.transform_dates,
                as_json=True,
            )
            data.extend(rows)
        return data


class ODataCaseSerializer(ODataBaseSerializer):

    metadata_url = ODataCaseMetadataView.urlname
    table_metadata_url = ODataCaseMetadataView.table_urlname

    def get_config(self, config_id):
        return CaseExportInstance.get(config_id)


class ODataFormSerializer(ODataBaseSerializer):

    metadata_url = ODataFormMetadataView.urlname
    table_metadata_url = ODataFormMetadataView.table_urlname

    def get_config(self, config_id):
        return FormExportInstance.get(config_id)
