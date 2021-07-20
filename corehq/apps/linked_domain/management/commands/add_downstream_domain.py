from django.core.management import BaseCommand

from corehq.apps.linked_domain.models import DomainLink


class Command(BaseCommand):
    """
    Links a remote domain as a downstream domain to a given upstream domain on this HQ
    """

    def add_arguments(self, parser):
        parser.add_argument('-r', '--url', required=True,
                            help="URL of downstream domain to link https://url.of.linked.hq/a/linked_domain_name/")
        parser.add_argument('-d', '--domain', required=True,
                            help="upsteam domain on this HQ.")

    def handle(self, url, domain, **options):
        DomainLink.link_domains(url, domain)
