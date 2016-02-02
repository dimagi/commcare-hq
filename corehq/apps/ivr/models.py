from corehq.apps.sms.mixin import UnrecognizedBackendException
from corehq.apps.sms.models import SQLMobileBackend, Log, CallLog
from dimagi.utils.couch.migration import SyncSQLToCouchMixin
from django.db import models


class UnrecognizedIVRBackendException(UnrecognizedBackendException):
    pass


class SQLIVRBackend(SQLMobileBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    def initiate_outbound_call(self, call, logged_subevent, ivr_data=None):
        """
        Should return False if an error occurred and the call should be retried.
        Should return True if the call should not be retried (either because it
        was queued successfully or because an unrecoverable error occurred).
        """
        raise NotImplementedError("Please implement this method")

    def get_response(self, gateway_session_id, ivr_responses, collect_input=False,
            hang_up=True, input_length=None):
        raise NotImplementedError("Please implement this method")

    def cache_first_ivr_response(self):
        """
        If you want the framework to cache the first response that HQ will have
        to the gateway, set this to True.
        """
        return False

    def set_first_ivr_response(self, call, gateway_session_id, ivr_data):
        call.xforms_session_id = ivr_data.session.session_id
        call.use_precached_first_response = True
        call.first_response = self.get_response(
            gateway_session_id,
            ivr_data.ivr_responses,
            collect_input=True,
            hang_up=False,
            input_length=ivr_data.input_length
        )


class Call(SyncSQLToCouchMixin, Log):
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    """ Call Metadata """

    # True if the call was answered, False if not
    answered = models.NullBooleanField(default=False)

    # Length of the call in seconds
    duration = models.IntegerField(null=True)

    # The session id returned from the backend, with the backend's hq api id
    # and a hyphen prepended. For example: TWILIO-xxxxxxxxxx
    gateway_session_id = models.CharField(max_length=126, null=True)

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

    @classmethod
    def _migration_get_fields(cls):
        return [
            'answered',
            'duration',
            'gateway_session_id',
            'submit_partial_form',
            'include_case_side_effects',
            'max_question_retries',
            'current_question_retry_count',
            'xforms_session_id',
            'error_message',
            'use_precached_first_response',
            'first_response',
            'case_id',
            'case_for_case_submission',
            'form_unique_id',
            'domain',
            'date',
            'couch_recipient_doc_type',
            'couch_recipient',
            'phone_number',
            'direction',
            'error',
            'system_error_message',
            'system_phone_number',
            'backend_api',
            'backend_id',
            'billed',
            'workflow',
            'xforms_session_couch_id',
            'reminder_id',
            'location_id',
            'messaging_subevent_id',
        ]

    @classmethod
    def _migration_get_couch_model_class(cls):
        return CallLog
