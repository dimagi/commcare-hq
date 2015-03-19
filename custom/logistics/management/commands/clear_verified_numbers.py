from django.core.management import BaseCommand
from corehq.apps.sms.mixin import VerifiedNumber
from custom.ewsghana.models import EWSGhanaConfig
from custom.ilsgateway.models import ILSGatewayConfig


class Command(BaseCommand):

    def handle(self, *args, **options):
        logistics_domains = ILSGatewayConfig.get_all_enabled_domains() + EWSGhanaConfig.get_all_enabled_domains()
        for domain in logistics_domains:
            verified_numbers = VerifiedNumber.by_domain(domain)
            print "Deleting verified numbers for domain: %s" % domain
            for verified_number in verified_numbers:
                verified_number.delete()
