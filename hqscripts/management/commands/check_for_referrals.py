from dimagi.utils.couch.database import iter_docs
from django.core.management.base import LabelCommand
from casexml.apps.case.models import CommCareCase


class Command(LabelCommand):
    help = "Check for cases that use referrals"
    args = ""
    label = ""

    def handle(self, *args, **options):
        db = CommCareCase.get_db()

        ids = (row['id'] for row in db.view('case/open_cases', reduce=False))

        for i, doc in enumerate(iter_docs(db, ids, chunksize=500)):
            if i % 1000 == 0:
                self.stderr.write('%s' % i)
            if doc.get('referrals'):
                try:
                    referral_date = filter(
                        None,
                        [r.get('modified_on') for r in doc['referrals']],
                    )[-1]
                except (TypeError, IndexError):
                    referral_date = 'N/A'
                self.stdout.write('%s\t%s\t%s\t%s' % (
                    doc.get('_id'), doc.get('domain'),
                    doc.get('server_modified_on'), referral_date,
                ))
