from .interface import PillowProcessor
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.util.quickcache import quickcache


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
            app = self._get_app(domain, build_id)

            if not app.has_submissions:
                app.has_submissions = True
                app.save()
                self._get_app.clear(self, domain, build_id)

    @quickcache(['domain', 'build_id'], timeout=60 * 60)
    def _get_app(self, domain, build_id):
        return get_app(domain, build_id)
