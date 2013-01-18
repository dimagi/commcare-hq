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

#        <data key="promoter_name">admin</data>
#        <data key="promoter_member_id">blah</data>
#        <data key="promoter_id">1</data>
        for user in CommCareUser.by_domain(PACT_DOMAIN):
            print "setting CHW user properties %s" % user.username
            user.user_data['promoter_name'] = user.raw_username
            user.user_data['promoter_member_id'] = 'blah' #retaining from pact
            if hasattr(user, 'old_user_id'):
                user.user_data['promoter_id'] = user.old_user_id
            user.save()


