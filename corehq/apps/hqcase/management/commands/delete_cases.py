from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand, CommandError

from couchdbkit import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain_by_owner
from corehq.form_processor.utils import should_use_sql_backend
from memoized import memoized
from dimagi.utils.couch.database import iter_bulk_delete
from corehq.apps.users.models import CouchUser, CommCareUser
from six.moves import input


class Command(BaseCommand):
    help = "Hard delete all cases owned by a given user.  (ID or username)"

    def add_arguments(self, parser):
        parser.add_argument(
            'user',
        )
        parser.add_argument(
            '--no-prompt',
            action='store_true',
            dest='no_prompt',
            help='Delete cases without prompting for confirmation',
        )

    @property
    @memoized
    def db(self):
        return CommCareCase.get_db()

    def delete_all(self):
        case_ids = get_case_ids_in_domain_by_owner(
            self.domain, self.user.user_id)
        iter_bulk_delete(self.db, case_ids)

    def handle(self, user, **options):
        try:
            self.user = CouchUser.get_by_username(user)
            if not self.user:
                self.user = CouchUser.get(user)
        except ResourceNotFound:
            print("Could not find user {}".format(user))
            return

        if not isinstance(self.user, CommCareUser):
            print ("Sorry, the user you specify has to be a mobile worker. "
                   "This changed when delete_cases was refactored to use "
                   "cases_by_owner/view instead of case/by_owner. "
                   "The new view needs an explicit domain, "
                   "and I didn't implement that for WebUsers who can belong "
                   "to multiple domains, but usually do not own cases.")
            exit(1)

        self.domain = self.user.domain

        if should_use_sql_backend(self.domain):
            raise CommandError('This command only works for couch-based domains.')

        if not options.get('no_prompt'):
            msg = "Delete all cases owned by {}? (y/n)\n".format(
                self.user.username,
            )
            if not input(msg) == 'y':
                print("cancelling")
                return

        self.delete_all()
        print("Cases successfully deleted, you monster!")
