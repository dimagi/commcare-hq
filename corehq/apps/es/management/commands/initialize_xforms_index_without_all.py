import copy

from django.core.management.base import BaseCommand

from corehq.elastic import get_es_new
from corehq.pillows.mappings.xform_mapping import XFORM_ES_TYPE, XFORM_MAPPING, XFORM_INDEX
from pillowtop.es_utils import ElasticsearchIndexInfo, initialize_index_and_mapping


class Command(BaseCommand):
    help = ("Adhoc command for ICDS xforms reindex")

    def add_arguments(self, parser):
        parser.add_argument(
            'index_name',
        )

    def handle(self, index_name, **options):
        mapping = copy.deepcopy(XFORM_MAPPING)
        mapping["_all"] = {"enabled": False}
        es = get_es_new()
        index_info = ElasticsearchIndexInfo(
            index=index_name,
            type=XFORM_ES_TYPE,
            mapping=mapping,
        )
        initialize_index_and_mapping(es, index_info)

        # tune settings for indexing speed
        es.indices.put_settings(
            index=index_name,
            body='''{
                "index": {
                    "refresh_interval": -1,
                    "number_of_replicas": 0,
                    "translog.durability": "async"
                }
            }'''
        )

        result = es.reindex({
            "source": {
                "index": XFORM_INDEX,
                "_source": {"exclude": ["_id"]}
            },
            "dest": {"index": index_name}
        }, wait_for_completion=False, request_timeout=300)
        print("Check for status ' curl -X GET "http://host:port/_tasks/?pretty&detailed=true&actions=*reindex"'")
