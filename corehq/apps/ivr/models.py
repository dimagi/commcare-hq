from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.mixin import UUIDGeneratorMixin
from corehq.apps.sms.mixin import UnrecognizedBackendException
from corehq.apps.sms.models import SQLMobileBackend, Log, OUTGOING
from django.db import models


class SQLIVRBackend(SQLMobileBackend):
    """
    IVR Functionality has been removed, but this model is being kept
    in order to preserve foreign key references in the Call model history.
    """
    class Meta(object):
        app_label = 'sms'
        proxy = True


class Call(UUIDGeneratorMixin, Log):
    """
    IVR Functionality has been removed, but this model is being kept
    in order to preserve the call history.
    """
    UUIDS_TO_GENERATE = ['couch_id']

    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    """ Call Metadata """

    # True if the call was answered, False if not
    answered = models.NullBooleanField(default=False)

    # Length of the call in seconds
    duration = models.IntegerField(null=True)

    # The session id returned from the backend, with the backend's hq api id
    # and a hyphen prepended. For example: TWILIO-xxxxxxxxxx
    gateway_session_id = models.CharField(max_length=126, null=True, db_index=True)

    """ Advanced IVR Options """

    # If True, on hangup, a partial form submission will occur if the
    # survey is not yet completed
    submit_partial_form = models.NullBooleanField(default=False)

    # Only matters when submit_partial_form is True.
    # If True, case side effects are applied to any partial form submissions,
    # otherwise they are excluded.
    include_case_side_effects = models.NullBooleanField(default=False)

    # The maximum number of times to retry a question with an invalid response
    # before hanging up
    max_question_retries = models.IntegerField(null=True)

    # A count of the number of invalid responses for the current question
    current_question_retry_count = models.IntegerField(default=0, null=True)

    """ IVR Framework Properties """

    # The session id from touchforms
    xforms_session_id = models.CharField(max_length=126, null=True)

    # Error message from the gateway, if any
    error_message = models.TextField(null=True)

    # This is set to True by the framework if the backend is preparing the first
    # IVR response when initiating the call. If True, then first_response is
    # the prepared first response
    use_precached_first_response = models.NullBooleanField(default=False)
    first_response = models.TextField(null=True)

    # The case id of the case to submit the form against
    case_id = models.CharField(max_length=126, null=True)
    case_for_case_submission = models.NullBooleanField(default=False)

    # The form unique id of the form that plays the survey for the call
    form_unique_id = models.CharField(max_length=126, null=True)

    class Meta(object):
        app_label = 'ivr'
