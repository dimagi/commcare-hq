from django.core.management.base import NoArgsCommand
import pytz
from corehq.apps.domain.models import Domain
import sys

class Command(NoArgsCommand):
    help = "Create or confirm pact domain"
    option_list = NoArgsCommand.option_list + (
    )
    def handle_noargs(self, **options):
        pact_domain = Domain.view('domain/domains', key='pact').all()[0]

        for django_user in django_user_dump:
            #WebUser()
            #rachel, ayana, others with full admin
            #chws with just report viewing/edit data
            pass




