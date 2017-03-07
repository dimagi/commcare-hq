from django.http import Http404

from dimagi.utils.parsing import string_to_utc_datetime

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.users.models import CouchUser, LastSubmission
from corehq.util.quickcache import quickcache
from corehq.apps.receiverwrapper.util import get_app_version_info

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
        app_id = doc.get('app_id')
        version = doc.get('version')

        try:
            metadata = doc['form']['meta']
        except KeyError:
            metadata = None

        if user_id and domain and received_on:
            mark_latest_submission(domain, user_id, app_id, build_id, version, metadata, received_on)


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


def mark_latest_submission(domain, user_id, app_id, build_id, version, metadata, received_on):
    user = CouchUser.get_by_user_id(user_id, domain)

    if not user:
        return

    try:
        received_on_datetime = string_to_utc_datetime(received_on)
    except ValueError:
        return

    last_submissions = filter(
        lambda submission: submission.app_id == app_id,
        user.reporting_metadata.last_submissions,
    )
    if last_submissions:
        assert len(last_submissions) == 1, 'Must only have one last submission per app'
        last_submission = last_submissions[0]
    else:
        last_submission = None

    app_version_info = get_app_version_info(
        domain,
        build_id,
        version,
        metadata
    )

    if last_submission is None or last_submission.submission_date < received_on_datetime:

        if last_submission is None:
            last_submission = LastSubmission()
            user.reporting_metadata.last_submissions.append(last_submission)

        last_submission.submission_date = received_on_datetime
        last_submission.device_id = metadata.get('deviceID')
        last_submission.app_id = app_id
        last_submission.build_id = build_id
        last_submission.build_version = app_version_info.build_version
        last_submission.commcare_version = app_version_info.commcare_version

        user.save()
