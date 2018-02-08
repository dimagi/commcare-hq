from __future__ import print_function

from __future__ import absolute_import
from django.core.management import BaseCommand

from corehq.apps.app_manager.models import LinkedApplication, RemoteAppDetails
from corehq.apps.linked_domain.remote_accessors import whilelist_app_on_remote


class Command(BaseCommand):
    """
    Creates a master and linked app pair for two existing apps were the master app is on a remote
    instance of CommCare HQ
    """

    def add_arguments(self, parser):
        parser.add_argument('-m', '--master_id', required=True,
                            help="ID of the master app on remote system")
        parser.add_argument('-l', '--linked_id', required=True,
                            help="ID of the local app to be linked")
        parser.add_argument('-r', '--url_base', required=True,
                            help="Base URL of remote system e.g. httpw://www.commcarehq.org")
        parser.add_argument('-d', '--domain', required=True,
                            help="Domain of master app.")
        parser.add_argument('-u', '--username', required=True,
                            help="Username for remote authentication")
        parser.add_argument('-k', '--api_key', required=True,
                            help="ApiKey for remote authentication")

    def handle(self, master_id, linked_id, url_base, domain, username, api_key, **options):
        remote_app_details = RemoteAppDetails(
            url_base,
            domain,
            username,
            api_key,
            master_id
        )

        linked_app = LinkedApplication.get(linked_id)
        whilelist_app_on_remote(domain, master_id, linked_app.domain, remote_app_details)

        linked_app.master = master_id
        linked_app.remote_url_base = url_base
        linked_app.master_domain = domain
        linked_app.remote_auth.username = username
        linked_app.remote_auth.api_key = api_key
        linked_app.version = 0
        linked_app.doc_type = 'LinkedApplication'
        linked_app.save()
