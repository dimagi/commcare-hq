from django.core.management import BaseCommand

from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    help = "Makes emails into lowercase"

    def handle(self, *args, **options):
        db = CouchUser.get_db()
        # This view includes users with base_doc == CouchUser-Deleted
        for res in db.view("users/by_default_phone", include_docs=True, reduce=False):
            doc = res['doc']
            # if this condition is met, the doc can't be wrapped
            if doc['email'] and not doc['email'].islower():
                print doc['email']
                doc['email'] = doc['email'].lower()
                try:
                    user = CouchUser.wrap_correctly(doc)
                    user.save()
                except:
                    print doc['_id'], "failed to save"
