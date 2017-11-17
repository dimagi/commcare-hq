from __future__ import print_function
from __future__ import absolute_import
from django.core.management import BaseCommand, CommandError

from corehq.apps.app_manager.dbaccessors import get_latest_released_app_version
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.views.utils import update_linked_app


class Command(BaseCommand):
    """
    Creates a master and linked app pair for two existing apps
    """

    def add_arguments(self, parser):
        parser.add_argument('master_id')
        parser.add_argument('linked_id')

    def handle(self, master_id, linked_id, **options):
        print("Linking apps")
        master_app = Application.get(master_id)
        master_version = get_latest_released_app_version(master_app.domain, master_id)
        if not master_version:
            raise CommandError(
                "Creating linked app failed."
                " Unable to get latest released version of your app."
                " Make sure you have at least one released build."
            )

        linked_app = Application.get(linked_id)

        if linked_app.domain not in master_app.linked_whitelist:
            master_app.linked_whitelist.append(linked_app.domain)
            master_app.save()

        linked_app.doc_type = 'LinkedApplication'
        linked_app.master = master_id
        linked_app.master_domain = master_app.domain
        linked_app.save()
        update_linked_app(linked_app)
