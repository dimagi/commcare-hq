from datetime import datetime
from corehq.apps.domain.utils import get_doc_ids
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.models import RepeatRecord


class Command(BaseCommand):
    """
    Prints the approximate last time a repeater was created/touched.
    """

    def handle(self, *args, **options):
        domain = args[0]
        db = Domain.get_db()
        doc_ids = get_doc_ids(domain, 'RepeatRecord', db)
        count = len(doc_ids)
        print 'found %s doc ids' % count
        latest = datetime.min
        latest_doc = None
        for i, doc in enumerate(iter_docs(db, doc_ids)):
            wrapped = RepeatRecord.wrap(doc)
            if i % 100 == 0:
                print 'checked %s / %s' % (i, count)
            if wrapped.last_checked and wrapped.last_checked > latest:
                latest = wrapped.last_checked
                latest_doc = wrapped
                print 'new latest: %s' % latest

        if latest_doc:
            print 'latest repeater date is %s' % latest
            print 'latest repeater is %s' % latest_doc._id
        else:
            print 'no relevant repeaters found'

