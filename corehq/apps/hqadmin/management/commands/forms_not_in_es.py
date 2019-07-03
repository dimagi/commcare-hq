from __future__ import absolute_import, unicode_literals

import inspect

from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.elastic import ES_DEFAULT_INSTANCE, ES_META, get_es_instance
from corehq.form_processor.interfaces.dbaccessors import FormAccessors

DOC_TYPES = ('XFormInstance', )
CHUNK_SIZE = 100


class Command(BaseCommand):
    """
    Returns a list of form IDs that are in Couch/SQL but not in Elasticsearch.

    Forms are XFormInstance doc type only; not deleted, archived, etc.

    Can be used in conjunction with republish_forms_rebuild_cases::

        $ ./manage.py forms_not_in_es <DOMAIN> > form_ids.txt
        $ ./manage.py republish_forms_rebuild_cases form_ids.txt

    """
    help = inspect.cleandoc(__doc__).split('\n')[0]

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        for form_id in form_ids_not_in_es(domain):
            print(form_id)


def form_ids_not_in_es(domain):
    form_ids = form_ids_in_domain(domain)
    for chunk_in_db in chunked(form_ids, CHUNK_SIZE):
        chunk_in_es = form_ids_in_es(chunk_in_db)
        not_in_es = set(chunk_in_db) - set(chunk_in_es)
        for form_id in not_in_es:
            yield form_id


def form_ids_in_domain(domain):
    form_accessor = FormAccessors(domain)
    for doc_type in DOC_TYPES:
        form_ids = form_accessor.get_all_form_ids_in_domain(doc_type=doc_type)
        for form_id in form_ids:
            yield form_id


def form_ids_in_es(form_ids):
    query = {"filter": {"ids": {"values": list(form_ids)}}}
    es_instance = get_es_instance(ES_DEFAULT_INSTANCE)
    es_meta = ES_META['forms']
    results = es_instance.search(es_meta.index, es_meta.type, query,
                                 params={'size': CHUNK_SIZE})
    if 'hits' in results:
        for hit in results['hits']['hits']:
            es_doc = hit['_source']
            yield es_doc['_id']
