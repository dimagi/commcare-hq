import abc

from django.conf import settings


class AbstractElasticsearchInterface(metaclass=abc.ABCMeta):
    def __init__(self, es):
        self.es = es

    def update_index_settings(self, index, settings_dict):
        return self.es.indices.put_settings(settings_dict, index=index)

    def create_doc(self, index, doc_type, doc_id, doc):
        # Field [_id] is a metadata field and cannot be added inside a document.
        # Use the index API request parameters.
        doc = {key: value for key, value in doc.items() if key != '_id'}
        self.es.create(index, doc_type, body=doc, id=doc_id)

    def get_doc(self, index, doc_type, doc_id):
        doc = self.es.get_source(index, doc_type, doc_id)
        doc['_id'] = doc_id
        return doc

    def update_doc(self, index, doc_type, doc_id, doc, params=None):
        self.es.index(index, doc_type, body=doc, id=doc_id, params=params)

    def update_doc_fields(self, index, doc_type, doc_id, fields, params=None):
        self.es.update(index, doc_type, doc_id, body={"doc": fields}, params=params)

    def delete_doc(self, index, doc_type, doc_id):
        self.es.delete(index, doc_type, doc_id)


class ElasticsearchInterface1(AbstractElasticsearchInterface):
    pass


class ElasticsearchInterface2(AbstractElasticsearchInterface):
    _deprecated_index_settings = (
        'merge.policy.merge_factor',
        'store.throttle.max_bytes_per_sec',
        'store.throttle.type',
    )

    def update_index_settings(self, index, settings_dict):
        assert set(settings_dict.keys()) == {'index'}, settings_dict.keys()
        settings_dict = {
            "index": {
                key: value for key, value in settings_dict['index'].items()
                if key not in self._deprecated_index_settings
            }
        }
        super(ElasticsearchInterface2, self).update_index_settings(index, settings_dict)


ElasticsearchInterface = {
    1: ElasticsearchInterface1,
    2: ElasticsearchInterface2,
}[settings.ELASTICSEARCH_MAJOR_VERSION]
