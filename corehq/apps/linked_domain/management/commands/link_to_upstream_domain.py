from django.core.management import BaseCommand

from corehq.apps.linked_domain.models import DomainLink, RemoteLinkDetails


class Command(BaseCommand):
    """
    Setup a domain on this HQ as a downstream domain to a remote upstream domain
    """

    def add_arguments(self, parser):
        parser.add_argument('-r', '--url_base', required=True,
                            help="Base URL of remote upstream HQ e.g. https://www.commcarehq.org")
        parser.add_argument('-m', '--upstream_domain', required=True,
                            help="Upstream master domain.")
        parser.add_argument('-u', '--username', required=True,
                            help="Username for remote authentication")
        parser.add_argument('-k', '--api_key', required=True,
                            help="ApiKey for remote authentication")
        parser.add_argument('-d', '--downstream_domain', required=True,
                            help="Downstream domain on this HQ.")

    def handle(self, url_base, upstream_domain, username, api_key, downstream_domain, **options):
        remote_details = RemoteLinkDetails(
            url_base=url_base,
            username=username,
            api_key=api_key
        )
        DomainLink.link_domains(downstream_domain, upstream_domain, remote_details)
