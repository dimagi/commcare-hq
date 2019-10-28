from nose.plugins import Plugin

from corehq.pillows.utils import get_all_expected_es_indices
from corehq.util.elastic import reset_es_index


class ElasticsearchPlugin(Plugin):
    name = 'elasticsearch'
    enabled = True

    def configure(self, options, conf):
        for es_info in get_all_expected_es_indices():
            reset_es_index(es_info)
