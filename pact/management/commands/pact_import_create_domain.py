from django.core.management.base import NoArgsCommand
import pytz
from corehq.apps.domain.models import Domain
import sys

class Command(NoArgsCommand):
    help = "Create or confirm pact domain"
    option_list = NoArgsCommand.option_list + (
    )
    def handle_noargs(self, **options):
        check_domain = Domain.view('domain/domains', key='pact').count()
        if check_domain == 1:
            print "Domain exists"
            sys.exit()
        else:
            from corehq.apps.users.models import WebUser
            from corehq.apps.domain.shortcuts import create_domain
            domain_name = 'pact'
            username = 'dmyung@dimagi.com'
            passwd =''
            domain = create_domain(domain_name)
            domain.default_timezone = "America/New_York"
            domain.project_type = 'hiv'
            domain.customer_type = 'plus'
            domain.save()

            couch_user = WebUser.view('users/by_username', key='dmyung@dimagi.com', include_docs=True).all()[0]
            couch_user.add_domain_membership(domain_name, is_admin=True)
            couch_user.save()
            print "pact domain created"




