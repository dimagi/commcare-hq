from dimagi.utils.couch.database import iter_docs
from django.core.management.base import LabelCommand
from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.models import ApplicationBase


class Command(LabelCommand):

    def handle(self, *args, **options):
        db = Domain.get_db()

        def get_doc_ids():
            for result in db.view(
                    'domain/domains',
                    reduce=False).all():
                yield result['id']
            for result in ApplicationBase.get_db().view(
                    'app_manager/applications',
                    startkey=[None],
                    endkey=[None, {}],
                    reduce=False):
                yield result['id']

        for doc in iter_docs(db, get_doc_ids()):
            if 'secure_submissions' not in doc:
                print 'Updated', doc.get('doc_type'), doc.get('_id')
                doc['secure_submissions'] = False
                db.save_doc(doc)
