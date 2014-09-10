from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMSLog, CallLog

class Command(BaseCommand):
    args = ""
    help = ("Sets a default value for all domains' "
        "send_to_duplicated_case_numbers property")

    def handle(self, *args, **options):
        for domain in Domain.get_all():
            count = (SMSLog.count_by_domain(domain.name) +
                CallLog.count_by_domain(domain.name))
            if count > 0:
                if not domain.send_to_duplicated_case_numbers:
                    # if not True, explicitly set to False
                    print "Setting %s to False" % domain.name
                    domain.send_to_duplicated_case_numbers = False
                    domain.save()
            else:
                print "Setting %s to True" % domain.name
                domain.send_to_duplicated_case_numbers = True
                domain.save()

