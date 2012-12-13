from corehq.apps.api.es import XFormES
from django.core.management.base import NoArgsCommand
from couchforms.models import XFormInstance
from pact.signals import process_dots_submission
from pact.utils import MISSING_DOTS_QUERY


CHUNK_SIZE=100

class Command(NoArgsCommand):
    help = "Helper command to compute DOT computed_ fields - to exteranlly operate that operation that should happen on signal firing on submission"
    option_list = NoArgsCommand.option_list + (
    )

    seen_doc_ids = {}

    def handle_noargs(self, **options):
        xform_es = XFormES()
        offset = 0

        q = MISSING_DOTS_QUERY
        q['size'] = CHUNK_SIZE

        while True:
            q['from'] = offset
            res = xform_es.run_query(q)
            print "####### Query block total: %s" % res['hits']['total']
            if len(res['hits'].get('hits', [])) == 0:
                break
            else:
                for hit in res['hits']['hits']:
                    doc_id = hit['_id']
                    if self.seen_doc_ids.has_key(doc_id):
                        continue
                    else:
                        self.seen_doc_ids[doc_id ] =1

                    xfdoc = XFormInstance.get(doc_id)

                    #quick sanity check
                    if hasattr(xfdoc, 'pact_dots_data'):
                        delattr(xfdoc, 'pact_dots_data')
                        xfdoc.save()
                        print "deleting property"

                    process_dots_submission(None, xfdoc, blocking=True)
                    #print "getting doc_id: %s" % doc_id
            offset += CHUNK_SIZE



