import json
from collections import Counter

from couchdbkit.ext.django.loading import couchdbkit_handler

from corehq.apps.dump_reload.couch.id_providers import LocationIDProvider, AppIdProvier
from corehq.apps.dump_reload.interface import DataDumper
from dimagi.utils.couch.database import iter_docs

APP_LABELS = {
    'locations.Location': LocationIDProvider(),
    'app_manager.Application': AppIdProvier(),
}


class CouchDataDumper(DataDumper):
    def dump(self, output_stream):
        stats = Counter()
        for label, id_provider in APP_LABELS.items():
            app_label, schema = label.split('.')
            doc_class = couchdbkit_handler.get_schema(app_label, schema.lower())
            ids = id_provider.get_doc_ids(self.domain)
            stats += _dump_docs(doc_class, ids, output_stream)
        return stats


def _dump_docs(doc_class, doc_ids, output_stream):
    stats = Counter()
    for doc in iter_docs(doc_class.get_db(), doc_ids):
        json.dump(doc, output_stream)
        output_stream.write('\n')
        stats.update(['{}.{}'.format(doc_class._meta.app_label, doc_class.__name__)])
    return stats
