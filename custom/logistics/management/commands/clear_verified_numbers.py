from django.core.management import BaseCommand
from corehq.apps.sms.mixin import VerifiedNumber


class Command(BaseCommand):

    def handle(self, *args, **options):
        logistics_domains = ['ewsghana-test-1', 'ilsgateway-test-1', 'ilsgateway-test-2']
        for domain in logistics_domains:
            verified_numbers = VerifiedNumber.by_domain(domain)
            print "Deleting verified numbers for domain: %s" % domain
            for verified_number in verified_numbers:
                verified_number.delete()
