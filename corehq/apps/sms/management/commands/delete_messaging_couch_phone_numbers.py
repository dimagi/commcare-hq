from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.mixin import VerifiedNumber
from dimagi.utils.couch.database import iter_bulk_delete_with_doc_type_verification
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Deletes all messaging phone numbers stored in couch")

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-interval",
            action="store",
            dest="delete_interval",
            type=int,
            default=5,
            help="The number of seconds to wait between each bulk delete.",
        )

    def get_couch_ids(self):
        result = VerifiedNumber.view(
            'phone_numbers/verified_number_by_domain',
            include_docs=False,
            reduce=False,
        ).all()
        return [row['id'] for row in result]

    def get_soft_deleted_couch_ids(self):
        result = VerifiedNumber.view(
            'all_docs/by_doc_type',
            startkey=['VerifiedNumber-Deleted'],
            endkey=['VerifiedNumber-Deleted', {}],
            include_docs=False,
            reduce=False,
        ).all()
        return [row['id'] for row in result]

    def delete_models(self, delete_interval):
        print('Deleting VerifiedNumbers...')
        count = iter_bulk_delete_with_doc_type_verification(
            VerifiedNumber.get_db(),
            self.get_couch_ids(),
            'VerifiedNumber',
            wait_time=delete_interval,
            max_fetch_attempts=5
        )
        print('Deleted %s documents' % count)

        print('Deleting Soft-Deleted VerifiedNumbers...')
        count = iter_bulk_delete_with_doc_type_verification(
            VerifiedNumber.get_db(),
            self.get_soft_deleted_couch_ids(),
            'VerifiedNumber-Deleted',
            wait_time=delete_interval,
            max_fetch_attempts=5
        )
        print('Deleted %s documents' % count)

    def handle(self, **options):
        self.delete_models(options['delete_interval'])
