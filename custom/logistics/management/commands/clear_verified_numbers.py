from django.core.management import BaseCommand
from corehq.apps.sms.mixin import VerifiedNumber


class Command(BaseCommand):

    def handle(self, *args, **options):
        for domain in args:
            verified_numbers = VerifiedNumber.by_domain(domain)
            print "Deleting verified numbers for domain: %s" % domain
            for verified_number in verified_numbers:
                verified_number.delete()
