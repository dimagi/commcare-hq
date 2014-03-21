from django.core.management.base import LabelCommand
from corehq import Domain
from corehq.apps.app_manager.models import ApplicationBase


class Command(LabelCommand):

    def handle(self, *args, **options):
        db = Domain.get_db()

        def get_docs():
            for result in db.view(
                    'domain/domains',
                    reduce=False,
                    include_docs=True).all():
                yield result['doc']
            for result in ApplicationBase.get_db().view(
                    'app_manager/applications',
                    startkey=[None],
                    endkey=[None, {}],
                    reduce=False,
                    include_docs=True):
                yield result['doc']

        for doc in get_docs():
            if 'secure_submissions' not in doc:
                print 'Updated', doc.get('doc_type'), doc.get('_id')
                doc['secure_submissions'] = False
                db.save_doc(doc)
