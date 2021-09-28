from django.core.management.base import BaseCommand

from corehq.apps.api.es import ReportFormESView
from corehq.apps.es import filters
from corehq.apps.es.forms import FormES
from pact.enums import PACT_DOMAIN, PACT_DOTS_DATA_PROPERTY


CHUNK_SIZE = 100


class Command(BaseCommand):
    help = "Helper command to compute DOT computed_ fields - to exteranlly operate that operation that should happen on signal firing on submission"

    seen_doc_ids = {}

    def handle(self, **options):
        xform_es = ReportFormESView(PACT_DOMAIN)
        offset = 0

        q = (
            FormES().remove_default_filters()
            .domain(PACT_DOMAIN)
            .filter(filters.term("form.#type", "dots_form"))
            .filter(filters.missing("%s.processed.#type" % PACT_DOTS_DATA_PROPERTY))
            .sort("received_on")
            .size(CHUNK_SIZE)
            .raw_query
        )

        while True:
#            q['from'] = offset
            res = xform_es.run_query(q)
            print("####### Query block total: %s" % res['hits']['total'])
            print(res['hits']['hits'])
            if len(res['hits'].get('hits', [])) == 0:
                break
            else:
                for hit in res['hits']['hits']:
                    doc_id = hit['_id']
                    if doc_id in self.seen_doc_ids:
                        continue
                    else:
                        self.seen_doc_ids[doc_id ] =1
            offset += CHUNK_SIZE
