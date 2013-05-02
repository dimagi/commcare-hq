from django.db.models import get_apps
from django.core.management.base import BaseCommand
from couchdbkit.ext.django.loading import couchdbkit_handler
from corehq import couchapps

class Command(BaseCommand):
    help = 'Copy temporary design docs over existing ones'

    def handle(self, *args, **options):
        # this is overridden so we can also do the trick on couchapps
        for app in get_apps():
            couchdbkit_handler.copy_designs(app, temp='tmp', verbosity=2)
        
        couchapps.copy_designs()
