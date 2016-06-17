from django.http import Http404

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.util.quickcache import quickcache

from .interface import PillowProcessor


class AppFormSubmissionTrackerProcessor(PillowProcessor):
    """
    Processor used to process each form and mark the corresponding application as
    having submissions (has_submissions = True).
    """

    def process_change(self, pillow_instance, change):
        if change.deleted:
            return

        doc = change.get_document()
        if not doc:
            return

        build_id = doc.get('build_id')
        domain = change.metadata.domain

        if build_id and domain:
            self._mark_has_submission(domain, build_id)

    @quickcache(['domain', 'build_id'], timeout=60 * 60)
    def _mark_has_submission(self, domain, build_id):
        app = None
        try:
            app = get_app(domain, build_id)
        except Http404:
            pass

        if app and not app.has_submissions:
            app.has_submissions = True
            app.save()
