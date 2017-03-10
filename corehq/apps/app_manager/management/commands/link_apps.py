from __future__ import print_function
from django.core.management import BaseCommand, CommandError

from corehq.apps.app_manager.models import Application


class Command(BaseCommand):
    """
    Creates a master and linked app pair for two existing apps
    """
    args = "master_app linked_app"

    def handle(self, *args, **options):
        if len(args) != 2:
            raise CommandError("Usage is ./manage.py link_apps %s" % self.args)
        print("Linking apps")
        master_id = args[0]
        linked_id = args[1]
        master_app = Application.get(master_id)
        linked_app = Application.get(linked_id)
        master_app.linked_whitelist.append(linked_app.domain)
        linked_app.doc_type = 'LinkedApplication'
        linked_app.master = master_id
        if master_app.version < linked_app.version:
            master_app.version = linked_app.version
        master_app.save()
        linked_app.save()
