from nose.plugins import Plugin

from corehq.elastic import get_es_new
from corehq.pillows.utils import get_all_expected_es_indices
from pillowtop.es_utils import initialize_index_and_mapping, \
    set_index_normal_settings


class ElasticsearchPlugin(Plugin):
    name = 'elasticsearch'
    enabled = True

    def configure(self, options, conf):
        es = get_es_new()
        for es_info in get_all_expected_es_indices():
            initialize_index_and_mapping(es, es_info)
            set_index_normal_settings(es, es_info.index)
