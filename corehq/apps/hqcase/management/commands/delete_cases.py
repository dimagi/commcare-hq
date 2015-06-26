from optparse import make_option
from django.core.management.base import NoArgsCommand, BaseCommand
from couchdbkit import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.dbaccessors import \
    get_number_of_cases_in_domain_by_owner, get_case_ids_in_domain_by_owner
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.couch.database import iter_bulk_delete
from corehq.apps.users.models import CouchUser, CommCareUser


class Command(BaseCommand):
    help = "Hard delete all cases owned by a given user.  (ID or username)"
    args = '<user>'

    option_list = NoArgsCommand.option_list + (
        make_option('--no-prompt',
                    action='store_true',
                    dest='no_prompt',
                    help='Delete cases without prompting for confirmation'),
    )

    @property
    @memoized
    def db(self):
        return CommCareCase.get_db()

    def get_case_count(self):
        return get_number_of_cases_in_domain_by_owner(
            self.domain, self.user.user_id)

    def delete_all(self):
        case_ids = get_case_ids_in_domain_by_owner(
            self.domain, self.user.user_id)
        iter_bulk_delete(self.db, case_ids)

    def handle(self, *args, **options):
        if not len(args):
            print "Usage: ./manage.py delete_cases <user>"
            return
        try:
            self.user = CouchUser.get_by_username(args[0])
            if not self.user:
                self.user = CouchUser.get(args[0])
        except ResourceNotFound:
            print "Could not find user {}".format(args[0])
            return

        if not isinstance(self.user, CommCareUser):
            print ("Sorry, the user you specify has to be a mobile worker. "
                   "This changed when delete_cases was refactored to use "
                   "hqcase/by_owner instead of case/by_owner. "
                   "The new view needs an explicit domain, "
                   "and I didn't implement that for WebUsers who can belong "
                   "to multiple domains, but usually do not own cases.")
            exit(1)

        self.domain = self.user.domain

        if not options.get('no_prompt'):
            msg = "Delete all {} cases {} by {}? (y/n)\n".format(
                self.get_case_count(),
                "owned",
                self.user.username,
            )
            if not raw_input(msg) == 'y':
                print "cancelling"
                return

        self.delete_all()
        print "Cases successfully deleted, you monster!"
