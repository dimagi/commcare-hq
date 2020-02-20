import copy

from django.core.management.base import BaseCommand
from django.conf import settings

from corehq.elastic import get_es_new
from corehq.pillows.mappings.xform_mapping import XFORM_ES_TYPE, XFORM_MAPPING, XFORM_INDEX
from pillowtop.es_utils import ElasticsearchIndexInfo, initialize_index_and_mapping


class Command(BaseCommand):
    help = ("Adhoc command for ICDS xforms reindex")

    def add_arguments(self, parser):
        parser.add_argument('index_name')
        parser.add_argument('number_of_shards', type=int)
        parser.add_argument('number_of_replicas', type=int)
        parser.add_argument(
            '-c',
            '--create-index',
            action='store_true',
            default=False,
            help="Create and initialize index but don't reindex",
        )
        parser.add_argument(
            '-r',
            '--do-reindex',
            action='store_true',
            default=False,
            help="Run reindex"
        )

    def handle(self, index_name, number_of_shards, number_of_replicas, **options):
        create_index = options.get('create_index')
        do_reindex = options.get('do_reindex')

        print(create_index, do_reindex)
        if create_index:
            mapping = copy.deepcopy(XFORM_MAPPING)
            mapping["_all"] = {"enabled": False}

            shard_settings = {
                'number_of_shards': number_of_shards, 'number_of_replicas': number_of_replicas
            }
            if settings.ES_SETTINGS and 'xforms' in settings.ES_SETTINGS:
                settings.ES_SETTINGS['xforms'].update(shard_settings)
            elif settings.ES_SETTINGS:
                settings.ES_SETTINGS['xforms'] = shard_settings
            else:
                settings.ES_SETTINGS = {'xforms': shard_settings}

            es = get_es_new()
            index_info = ElasticsearchIndexInfo(
                index=index_name,
                type=XFORM_ES_TYPE,
                mapping=mapping,
            )
            initialize_index_and_mapping(es, index_info)

        if do_reindex:
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
            print(result)
            print("""Check for status 'curl -X GET "http://host:port/_tasks/?pretty&detailed=true&actions=*reindex"'""")
