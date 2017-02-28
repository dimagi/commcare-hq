from django.http import Http404

from dimagi.utils.parsing import string_to_utc_datetime

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.users.models import CouchUser
from corehq.util.quickcache import quickcache

from .interface import PillowProcessor


class FormSubmissionMetadataTrackerProcessor(PillowProcessor):
    """
    Processor used to process each form and mark the corresponding application as
    having submissions (has_submissions = True).
    """

    def process_change(self, pillow_instance, change):
        if change.deleted or change.metadata is None:
            return

        doc = change.get_document()
        if not doc:
            return

        build_id = doc.get('build_id')
        domain = change.metadata.domain

        if build_id and domain:
            # Marks if a build has a submission. The function is cached based on domain
            # and build_id so that there is no need to fetch the app again after this
            # is called. Any subsequent calls with the same arguments will result in
            # the same effect, an app having has_submissions set to True.
            mark_has_submission(domain, build_id)

        user_id = doc.get('user_id')
        received_on = doc.get('received_on')

        if user_id and domain and received_on:
            mark_latest_submission(domain, user_id, received_on)


@quickcache(['domain', 'build_id'], timeout=60 * 60)
def mark_has_submission(domain, build_id):
    app = None
    try:
        app = get_app(domain, build_id)
    except Http404:
        pass

    if app and not app.has_submissions:
        app.has_submissions = True
        app.save()


def mark_latest_submission(domain, user_id, received_on):
    user = CouchUser.get_by_user_id(user_id, domain)

    if not user:
        return

    try:
        received_on_datetime = string_to_utc_datetime(received_on)
    except ValueError:
        return

    current_last_submission = user.reporting_metadata.last_submission_date

    if current_last_submission is None or current_last_submission < received_on_datetime:
        user.reporting_metadata.last_submission_date = received_on_datetime
        user.save()
