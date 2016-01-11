from collections import namedtuple
from django.core.management import BaseCommand
from dimagi.utils.chunked import chunked
from corehq.util.couch import send_keys_to_couch, IterDB
from corehq.util.couchdb_management import couch_config

Results = namedtuple('Results', ['restored', 'not_found', 'not_deleted'])


def get_deleted_doc(db, doc_id, rev):
    res = db.get(doc_id, revs=True, rev=rev)
    start = res['_revisions']['start']
    ids = res['_revisions']['ids']
    prev_revision = "{}-{}".format(start-1, ids[1])
    doc = db.get(doc_id, rev=prev_revision)
    doc.pop('_rev')
    return doc


def undelete_docs(db, doc_ids):
    results = Results(set(), set(), set())
    with IterDB(db) as iter_db:
        for chunk in chunked(set(doc_ids), 100):
            for res in send_keys_to_couch(db, keys=set(chunk)):

                print "\nDOC RESULT"
                doc_id = res['key']
                doc = res.get('doc')
                print doc_id
                print doc
                print res

                if res.get('error', None) == 'not_found':
                    results.not_found.add(doc_id)
                elif res.get('value', {}).get('deleted', False):
                    iter_db.save(
                        get_deleted_doc(db, doc_id, res['value']['rev'])
                    )
                    results.restored.add(doc_id)
                else:
                    results.not_deleted.add(doc_id)
    return results


class Command(BaseCommand):
    help = 'Delete document conflicts'

    def handle(self, *args, **options):
        #  print args
        #  print options
        doc_ids = ["idontwantthisfixture", "thisfixtureisntdeleted", "thisonedoesntexist"]
        # TODO get from cmdline - use 'fixtures'
        db = couch_config.all_dbs_by_slug[None]
        results = undelete_docs(db, doc_ids)
        print "RESTORED:", results.restored
        print "NOT_FOUND:", results.not_found
        print "NOT_DELETED:", results.not_deleted
