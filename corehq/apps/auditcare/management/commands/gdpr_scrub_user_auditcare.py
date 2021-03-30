import logging

from django.core.management.base import BaseCommand

from ...utils.export import navigation_events_by_user

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Scrub a username from auditcare for GDPR compliance"""
    new_username = "Redacted User (GDPR)"

    def add_arguments(self, parser):
        parser.add_argument('username', help="Username to scrub")

    def handle(self, username, **options):
        events = navigation_events_by_user(username)
        events.query.update(user=self.new_username)
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
