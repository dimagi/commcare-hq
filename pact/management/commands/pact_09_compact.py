from corehq.apps.cloudcare.models import CaseSpec, CasePropertySpec, SelectChoice
from django.core.management.base import NoArgsCommand
from couchforms.models import XFormInstance
from pact.enums import PACT_DOMAIN, PACT_CASE_TYPE, PACT_HP_CHOICES, GENDER_CHOICES, PACT_DOT_CHOICES

class Command(NoArgsCommand):
    help = "Create or update the CaseSpec for PACT Cases"
    option_list = NoArgsCommand.option_list + (
    )

    def handle_noargs(self, **options):
        casedb = XFormInstance.get_db()
        casedb.compact()



