from django.core.management.base import BaseCommand

from corehq.elastic import get_es_new
from corehq.util.dates import iso_string_to_datetime
from elasticsearch.helpers import reindex


class Command(BaseCommand):
    help = ("Adhoc command for ICDS xforms reindex using scan and bulk insert API")

    def add_arguments(self, parser):
        parser.add_argument('index_name')
        parser.add_argument('start_date', type=int)
        parser.add_argument('end_date', type=int)

    def handle(self, index_name, start_date, end_date, **options):
        es = get_es_new()
        start_date = self._get_last_start_date(es, index_name, start_date, end_date)
        query = {
            "sort": {"server_modified_on": {"order": "asc"}},
            "query": {
                "range": {
                    "server_modified_on": {
                        "gte": start_date,
                        "lte": end_date,
                        "format": "yyyy-MM-dd"
                    }
                }
            }
        }
        old_index = "xforms"  # alias
        reindex(es, old_index, index_name, query=query, chunk_size=100, scroll='100m',
            bulk_kwargs={"_source_excludes": ["_id"]})

    def _get_last_start_date(self, es, index_name, start_date, end_date):
        query = {
            "sort": {"server_modified_on": {"order": "asc"}},
            "query": {
                "range": {
                    "server_modified_on": {
                        "gte": start_date,
                        "lte": end_date,
                        "format": "yyyy-MM-dd"
                    }
                }
            },
            "_source": ["server_modified_on"],
            "from": 0,
            "size": 1
        }
        result = es.search(index_name, body=query)
        hits = result['hits']
        if not hits:
            return start_date
        else:
            return str(iso_string_to_datetime(hits[0]['_source']['server_modified_on']))
