import json
from collections import Counter

import itertools

from corehq.apps.dump_reload.couch.id_providers import DocTypeIDProvider
from corehq.apps.dump_reload.interface import DataDumper
from dimagi.utils.couch.database import iter_docs

DOC_PROVIDERS = {
    DocTypeIDProvider(['Location']),
    DocTypeIDProvider(['Application']),
}


class CouchDataDumper(DataDumper):
    slug = 'couch'

    def dump(self, output_stream):
        stats = Counter()
        for doc_class, doc_ids in get_doc_ids_to_dump(self.domain):
            stats += _dump_docs(doc_class, doc_ids, output_stream)
        return stats


def _dump_docs(doc_class, doc_ids, output_stream):
    model_label = '{}.{}'.format(doc_class._meta.app_label, doc_class.__name__)
    count = 0
    for doc in iter_docs(doc_class.get_db(), doc_ids):
        count += 1
        json.dump(doc, output_stream)
        output_stream.write('\n')
    return Counter({model_label: count})


def get_doc_ids_to_dump(domain):
    """
    :return: A generator of (doc_class, list(doc_ids))
    """
    for id_provider in DOC_PROVIDERS:
        yield itertools.chain(*id_provider.get_doc_ids(domain))
