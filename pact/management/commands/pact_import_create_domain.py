from django.core.management.base import NoArgsCommand
import pytz
from corehq.apps.domain.models import Domain
import sys
from pact.management.commands.constants import PACT_DOMAIN
from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain
import getpass

class Command(NoArgsCommand):
    help = "Create or confirm pact domain"
    option_list = NoArgsCommand.option_list + (
    )
    def handle_noargs(self, **options):
        check_domain = Domain.view('domain/domains', key=PACT_DOMAIN).count()
        if check_domain == 1:
            print "Domain exists"
        else:
            domain_name = PACT_DOMAIN
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


        #create pact domain import user
        if WebUser.get_by_username('pactimporter') is None:
            print "Pact importer user not created - creating"
            importerpassword = getpass.getpass("""\tEnter pact importer password: """)
            if importerpassword == "":
                return

            WebUser.create(PACT_DOMAIN, 'pactimporter', importerpassword,  email='dmyung+pactimporter@dimagi.com')
            print "pact importer created"





