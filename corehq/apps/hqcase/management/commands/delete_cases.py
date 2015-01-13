from optparse import make_option
from django.core.management.base import NoArgsCommand, BaseCommand
from couchdbkit import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.couch.database import iter_bulk_delete
from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    help = "Hard delete all cases owned by a given user.  (ID or username)"
    args = '<user>'

    option_list = NoArgsCommand.option_list + (
        make_option('--no-prompt',
                    action='store_true',
                    dest='no_prompt',
                    help='Delete cases without prompting for confirmation'),
        make_option('--by-last-submitter',
                    action='store_true',
                    dest='last_submitter',
                    help='delete cases last updated by the specified user'),
    )

    @property
    @memoized
    def db(self):
        return CommCareCase.get_db()

    def case_query(self, reduce=False):
        if self.last_submitter:
            view_name = 'case/by_user'
        else:
            view_name = 'case/by_owner'
        return self.db.view(
            view_name,
            startkey=[self.user.user_id],
            endkey=[self.user.user_id, {}],
            reduce=reduce,
        )

    def get_case_count(self):
        res = self.case_query(reduce=True).one()
        return res['value'] if res else 0

    def delete_all(self):
        case_ids = [r["id"] for r in self.case_query(reduce=False)]
        iter_bulk_delete(self.db, case_ids)

    def handle(self, *args, **options):
        self.last_submitter = options.get('last_submitter', False)
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

        if not options.get('no_prompt'):
            msg = "Delete all {} cases {} by {}? (y/n)\n".format(
                self.get_case_count(),
                "submitted" if self.last_submitter else "owned",
                self.user.username,
            )
            if not raw_input(msg) == 'y':
                print "cancelling"
                return

        self.delete_all()
        print "Cases successfully deleted, you monster!"
