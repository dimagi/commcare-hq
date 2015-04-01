from optparse import make_option
from dimagi.utils.couch.database import iter_docs, get_db
from django.core.management.base import BaseCommand, LabelCommand


class Command(BaseCommand):
    help = 'Delete document conflicts'

    option_list = LabelCommand.option_list + (
        make_option(
            '--limit',
            action='store',
            type='int',
            dest='limit',
            default=1000,
            help="Only process this many docs."),
    )

    def handle(self, *args, **options):
        db = get_db()
        results = db.view('doc_conflicts/conflicts', reduce=False, limit=options['limit'])
        total = results['total_rows']
        ids = [row['id'] for row in results]
        to_delete = []
        print('Processing {} of {} docs'.format(len(ids), total))
        for doc in iter_docs(db, ids, conflicts=True):
            conflicts = doc.get('_conflicts', [])
            doc_id = doc['_id']
            print('Deleting {} conflicts for doc: {}'.format(len(conflicts), doc_id))
            for rev in conflicts:
                to_delete.append({
                    '_id': doc_id,
                    '_rev': rev
                })

        db.bulk_delete(to_delete)
        print('{} doc revisions deleted'.format(len(to_delete)))
