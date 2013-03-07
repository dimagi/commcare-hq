from django.conf import settings
from corehq.apps.domain.models import Domain
from pillowtop.listener import ElasticPillow

class ExchangePillow(ElasticPillow):
    document_class = Domain
    couch_filter = "domain/all_domains"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_index = "cc_exchange"
    es_type = "domain"
    es_meta = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "lowercase_analyzer": {
                        "type": "custom",
                        "tokenizer": "keyword",
                        "filter": ["lowercase"]},
                    "comma": {
                        "type": "pattern",
                        "pattern": "\s*,\s*"}}}},
        "mappings": {
            "domain": {
                "properties": {
                    "license": {"type": "string", "index": "not_analyzed"},
                    "deployment.region": {"type": "string", "analyzer": "lowercase_analyzer"},
                    "author": {"type": "string", "analyzer": "lowercase_analyzer"},
                    "project_type": {"type": "string", "analyzer": "comma"}}}}}