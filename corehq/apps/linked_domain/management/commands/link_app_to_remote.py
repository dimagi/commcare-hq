from django.core.management import BaseCommand

from corehq.apps.app_manager.models import LinkedApplication
from corehq.apps.app_manager.views.utils import update_linked_app
from corehq.apps.linked_domain.applications import link_app
from corehq.apps.linked_domain.models import RemoteLinkDetails


class Command(BaseCommand):
    """
    Creates a master and linked app pair for two existing apps were the master app is on a remote
    instance of CommCare HQ
    """

    def add_arguments(self, parser):
        parser.add_argument('-D', '--downstream_id', required=True,
                            help="ID of the app on the local system")
        parser.add_argument('-U', '--upstream_id', required=True,
                            help="ID of the app on the remote system")
        parser.add_argument('-r', '--url_base', required=True,
                            help="Base URL of remote system e.g. https://www.commcarehq.org")
        parser.add_argument('-d', '--domain', required=True,
                            help="Domain of master app.")
        parser.add_argument('-u', '--username', required=True,
                            help="Username for remote authentication")
        parser.add_argument('-k', '--api_key', required=True,
                            help="ApiKey for remote authentication")

    def handle(self, downstream_id, upstream_id, url_base, domain, username, api_key, **options):
        remote_details = RemoteLinkDetails(
            url_base,
            username,
            api_key,
        )

        linked_app = LinkedApplication.get(downstream_id)
        link_app(linked_app, domain, upstream_id, remote_details)
        update_linked_app(linked_app, upstream_id, 'system')
