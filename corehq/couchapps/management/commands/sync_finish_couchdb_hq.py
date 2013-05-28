from django.db.models import get_apps
from django.core.management.base import BaseCommand
from couchdbkit.ext.django.loading import couchdbkit_handler
from corehq import couchapps


# TODO: this should be moved to the same place as sync_prepare_couchdb_multi (currently in dimagi-utils)
class Command(BaseCommand):
    help = 'Copy temporary design docs over existing ones'

    def handle(self, *args, **options):
        # this is overridden so we can also do the trick on couchapps
        for app in get_apps():
            couchdbkit_handler.copy_designs(app, temp='tmp', verbosity=2)

        couchapps.copy_designs()

        try:
            import mvp_apps
        except ImportError:
            pass
        else:
            mvp_apps.copy_designs()

        try:
            from fluff import sync_couchdb as fluff_sync
        except ImportError:
            pass
        else:
            fluff_sync.copy_designs()
