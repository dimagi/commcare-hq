from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import timedelta

from django.conf import settings
from django.http import Http404

from corehq.apps.users.util import update_device_meta, update_latest_builds, filter_by_app
from dimagi.utils.parsing import string_to_utc_datetime

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.users.models import CouchUser, LastSubmission, DeviceAppMeta
from corehq.pillows.utils import format_form_meta_for_es
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.quickcache import quickcache
from corehq.apps.receiverwrapper.util import get_app_version_info

from .interface import PillowProcessor
import six


class FormSubmissionMetadataTrackerProcessor(PillowProcessor):
    """
    Processor used to process each form and mark the corresponding application as
    having submissions (has_submissions = True).
    """

    def process_change(self, change):
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

        user_id = doc.get('form', {}).get('meta', {}).get('userID')
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


def _last_submission_needs_update(last_submission, received_on_datetime, build_version,
                                  cc_version, debounce=True):
    # If debounce is true this function reduces load on the user db by  updating form submission
    # metadata no more than once every 15 minutes unless something else has changed.
    # That way if a user submits 10s or 100s of forms at once we do not need to write all of them.
    # If debounce is false it updates if the submission is newer at all
    if not (last_submission and last_submission.submission_date):
        return True
    time_difference = received_on_datetime - last_submission.submission_date
    debounce_delay = settings.USER_REPORTING_METADATA_UPDATE_FREQUENCY
    update_frequency = timedelta(minutes=debounce_delay) if debounce else timedelta(seconds=0)
    if time_difference > update_frequency:
        return True
    if build_version != last_submission.build_version:
        return True
    if cc_version != last_submission.commcare_version:
        return True
    return False


def mark_latest_submission(domain, user_id, app_id, build_id, version, metadata, received_on):
    user = CouchUser.get_by_user_id(user_id, domain)

    if not user or user.is_deleted():
        return

    try:
        received_on_datetime = string_to_utc_datetime(received_on)
    except ValueError:
        return

    last_submission = filter_by_app(user.reporting_metadata.last_submissions, app_id)

    if metadata and metadata.get('appVersion'):
        if not isinstance(metadata['appVersion'], six.string_types):
            metadata = format_form_meta_for_es(metadata)
        else:
            soft_assert_type_text(metadata['appVersion'])

    app_version_info = get_app_version_info(
        domain,
        build_id,
        version,
        metadata
    )

    if _last_submission_needs_update(last_submission,
                                     received_on_datetime,
                                     app_version_info.build_version,
                                     app_version_info.commcare_version):

        if last_submission is None:
            last_submission = LastSubmission()
            user.reporting_metadata.last_submissions.append(last_submission)

        last_submission.submission_date = received_on_datetime
        device_id = metadata.get('deviceID')
        last_submission.device_id = device_id
        last_submission.app_id = app_id
        last_submission.build_id = build_id
        last_submission.build_version = app_version_info.build_version
        last_submission.commcare_version = app_version_info.commcare_version

        if app_version_info.build_version:
            update_latest_builds(user, app_id, received_on_datetime, app_version_info.build_version)

        if _last_submission_needs_update(user.reporting_metadata.last_submission_for_user,
                                         received_on_datetime,
                                         app_version_info.build_version,
                                         app_version_info.commcare_version,
                                         False):

            user.reporting_metadata.last_submission_for_user = last_submission

        app_meta = DeviceAppMeta(
            app_id=app_id,
            build_id=build_id,
            last_submission=received_on_datetime,
        )
        update_device_meta(user, device_id, app_version_info.commcare_version, app_meta, save=False)

        user.save()
