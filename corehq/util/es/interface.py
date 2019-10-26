class ElasticsearchInterface(object):
    def __init__(self, es):
        self.es = es

    def update_index_settings(self, index, settings_dict):
        return self.es.indices.put_settings(settings_dict, index=index)
