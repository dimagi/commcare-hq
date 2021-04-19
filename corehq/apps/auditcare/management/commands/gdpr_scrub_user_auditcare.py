import logging

from django.core.management.base import BaseCommand

from ...models import AccessAudit, NavigationEventAudit

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Scrub a username from auditcare for GDPR compliance"""
    new_username = "Redacted User (GDPR)"

    def add_arguments(self, parser):
        parser.add_argument('username', help="Username to scrub")

    def handle(self, username, **options):
        def update_events(model):
            user_events = model.objects.filter(user=username)
            user_events.update(user=self.new_username)

        update_events(AccessAudit)
        update_events(NavigationEventAudit)
        self.scrub_legacy_couch_events(username)

    def scrub_legacy_couch_events(self, username):
        from couchdbkit.ext.django.loading import get_db
        from corehq.util.couch import DocUpdate, iter_update
        from corehq.util.log import with_progress_bar

        def update_username(event_dict):
            event_dict['user'] = self.new_username
            return DocUpdate(doc=event_dict)

        db = get_db("auditcare")
        results = db.view(
            'auditcare/urlpath_by_user_date',
            startkey=[username],
            endkey=[username, {}],
            reduce=False,
            include_docs=False,
        )
        doc_ids = {r["id"] for r in results}
        iter_update(db, update_username, with_progress_bar(doc_ids))
