from django.core.management.base import NoArgsCommand
from corehq.apps.users.models import  UserRole, CommCareUser, Permissions, CouchUser
from pact.enums import PACT_DOMAIN

REPORT_VIEWS_ROLE = "PACT CHW"

class Command(NoArgsCommand):
    help = "Apply roles to the PACT mobile workers"
    option_list = NoArgsCommand.option_list + (
    )
    def handle_noargs(self, **options):
        pact_chw_role = UserRole.get_or_create_with_permissions(PACT_DOMAIN, Permissions(view_reports=True, edit_data=True), name=REPORT_VIEWS_ROLE)
        for user in CommCareUser.by_domain(PACT_DOMAIN):
            print "setting CHW role for %s" % user.username
            user.set_role(PACT_DOMAIN, pact_chw_role.get_qualified_id())
            user.save()

