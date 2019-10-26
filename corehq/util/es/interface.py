import abc

from django.conf import settings


class AbstractElasticsearchInterface(metaclass=abc.ABCMeta):
    def __init__(self, es):
        self.es = es

    def update_index_settings(self, index, settings_dict):
        return self.es.indices.put_settings(settings_dict, index=index)


class ElasticsearchInterface1(AbstractElasticsearchInterface):
    pass


class ElasticsearchInterface2(AbstractElasticsearchInterface):
    _deprecated_index_settings = (
        'merge.policy.merge_factor',
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
