import uuid
from collections import namedtuple
from datetime import timedelta

from django.core.cache import cache
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_noop

from couchdbkit import MultipleResultsFound

from corehq import toggles
from corehq.apps.formplayer_api.smsforms.api import TouchformsError
from corehq.apps.sms.mixin import BadSMSConfigException, apply_leniency
from corehq.apps.sms.models import PhoneNumber
from corehq.apps.sms.util import strip_plus
from corehq.form_processor.models import XFormInstance
from corehq.messaging.scheduling.util import utcnow
from corehq.util.metrics import metrics_counter
from corehq.util.quickcache import quickcache
from dimagi.utils.couch import CriticalSection

XFORMS_SESSION_SMS = "SMS"
XFORMS_SESSION_IVR = "IVR"
XFORMS_SESSION_TYPES = [XFORMS_SESSION_SMS, XFORMS_SESSION_IVR]


class SQLXFormsSession(models.Model):
    """
    Keeps information about an SMS XForm session.
    """
    # Maximum session length of 7 days
    MAX_SESSION_LENGTH = 7 * 24 * 60

    STATUS_PARTIALLY_COMPLETE = "partially_completed"
    STATUS_COMPLETE = "completed"
    # "In Progress" means the survey session is open and the survey can still
    # be completed by the user
    STATUS_IN_PROGRESS = "in-progress"
    # "Not Finished" means the survey session closed without generating a form submission
    # and the survey can no longer be completed
    STATUS_NOT_FINISHED = "not-finished"

    STATUS_DISPLAY = {
        STATUS_PARTIALLY_COMPLETE: gettext_noop('Completed (Partially Completed Submission)'),
        STATUS_COMPLETE: gettext_noop('Completed'),
        STATUS_IN_PROGRESS: gettext_noop('In Progress'),
        STATUS_NOT_FINISHED: gettext_noop('Not Finished'),
    }

    # generic properties
    couch_id = models.CharField(db_index=True, max_length=50)
    connection_id = models.CharField(null=True, blank=True, db_index=True, max_length=50)
    session_id = models.CharField(null=True, blank=True, db_index=True, max_length=50)
    form_xmlns = models.CharField(null=True, blank=True, max_length=100)
    start_time = models.DateTimeField()
    modified_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)

    # True if all the questions in the survey were answered.
    completed = models.BooleanField(default=False)

    # HQ specific properties
    domain = models.CharField(null=True, blank=True, db_index=True, max_length=100)
    user_id = models.CharField(null=True, blank=True, max_length=50)
    app_id = models.CharField(null=True, blank=True, max_length=50)
    submission_id = models.CharField(null=True, blank=True, max_length=50)
    survey_incentive = models.CharField(null=True, blank=True, max_length=100)
    session_type = models.CharField(max_length=10, choices=list(zip(XFORMS_SESSION_TYPES, XFORMS_SESSION_TYPES)),
                                    default=XFORMS_SESSION_SMS)
    workflow = models.CharField(null=True, blank=True, max_length=20)
    reminder_id = models.CharField(null=True, blank=True, max_length=50)

    # The phone number to use for correspondence on this survey
    phone_number = models.CharField(max_length=126)

    # The number of minutes after which this session should expire, starting from the start_date.
    expire_after = models.IntegerField()

    # True if the session is still open. An open session allows answers to come in to the survey.
    session_is_open = models.BooleanField(default=True)

    # A list of integers representing the intervals, in minutes, that reminders should be sent.
    # A reminder in this context just sends the current question of an open survey to the contact
    # in order to remind them to answer it. This can be empty list if no reminders are desired.
    reminder_intervals = models.JSONField(default=list)

    # A zero-based index pointing to the entry in reminder_intervals which represents the
    # currently scheduled reminder.
    current_reminder_num = models.IntegerField(default=0)

    # The date and time that the survey framework must take the next action, which would be
    # either sending a reminder or closing the survey session.
    current_action_due = models.DateTimeField()

    # If True, when the session expires, the form will be submitted with any information collected
    # and the rest of the questions left blank.
    submit_partially_completed_forms = models.BooleanField(null=True)

    # Only matters when submit_partially_completed_forms is True.
    # If True, any case changes will be included in the submission.
    # If False, any case changes will be removed from the submission.
    include_case_updates_in_partial_submissions = models.BooleanField(null=True)

    class Meta(object):
        app_label = 'smsforms'
        index_together = [
            ['session_is_open', 'current_action_due'],
            ['session_is_open', 'connection_id'],
        ]

    def __str__(self):
        return 'Form %(form)s in domain %(domain)s. Last modified: %(mod)s' % \
            {"form": self.form_xmlns,
             "domain": self.domain,
             "mod": self.modified_time}

    @property
    def _id(self):
        return self.couch_id

    def close(self, force=True):
        from corehq.apps.smsforms.app import submit_unfinished_form

        if not self.session_is_open:
            return

        if self.submit_partially_completed_forms:
            try:
                submit_unfinished_form(self)
            except TouchformsError as e:
                if not force:
                    # Allow caller to handle and potentially retry
                    raise e

        self.mark_completed(False)

    def mark_completed(self, completed):
        self.session_is_open = False
        self.completed = completed
        self.modified_time = self.end_time = utcnow()
        if toggles.ONE_PHONE_NUMBER_MULTIPLE_CONTACTS.enabled(self.domain):
            XFormsSessionSynchronization.release_channel_for_session(self)

        metrics_counter('commcare.smsforms.session_ended', 1, tags={
            'domain': self.domain,
            'workflow': self.workflow,
            'status': (
                'success' if self.completed and self.submission_id else
                'terminated_partial_submission' if not self.completed and self.submission_id else
                'terminated_without_submission' if not self.completed and not self.submission_id else
                # Not sure if/how this could ever happen, but worth tracking if it does
                'completed_without_submission'
            )
        })
        self.save()
        subevent = self.related_subevent
        if subevent:
            subevent.update_date_last_activity()

    @property
    def related_subevent(self):
        subevents = self.messagingsubevent_set.all().order_by("-date", "-id")[:1]
        return subevents[0] if subevents else None

    @property
    def status(self):
        return self.STATUS_DISPLAY[self.status_slug]

    @property
    def status_slug(self):
        xform_instance = None
        if self.submission_id:
            xform_instance = XFormInstance.objects.get_form(self.submission_id, self.domain)

        if xform_instance:
            if xform_instance.partial_submission:
                return self.STATUS_PARTIALLY_COMPLETE
            else:
                return self.STATUS_COMPLETE
        elif self.session_is_open and self.session_type == XFORMS_SESSION_SMS:
            return self.STATUS_IN_PROGRESS
        else:
            return self.STATUS_NOT_FINISHED

    @classmethod
    def get_all_open_sms_sessions(cls, domain, contact_id):
        return cls.objects.filter(
            Q(session_type__isnull=True) | Q(session_type=XFORMS_SESSION_SMS),
            domain=domain,
            connection_id=contact_id,
            session_is_open=True,
        )

    @classmethod
    def close_all_open_sms_sessions(cls, domain, contact_id):
        sessions = cls.get_all_open_sms_sessions(domain, contact_id)
        for session in sessions:
            session.close()

    @classmethod
    def by_session_id(cls, id):
        try:
            return cls.objects.get(session_id=id)
        except SQLXFormsSession.DoesNotExist:
            return None

    @classmethod
    def get_open_sms_session(cls, domain, contact_id):
        """
        Looks up the open sms survey session for the given domain and contact_id.
        Only one session is expected to be open at a time.
        Raises MultipleResultsFound if more than one session is open.
        """
        objs = cls.get_all_open_sms_sessions(domain, contact_id).all()
        if len(objs) > 1:
            raise MultipleResultsFound('more than 1 ({}) session found for domain {} and contact {}'.format(
                len(objs), domain, contact_id
            ))
        elif len(objs) == 0:
            return None
        return objs[0]

    @classmethod
    def create_session_object(cls, domain, contact, phone_number, app, form, expire_after=MAX_SESSION_LENGTH,
            reminder_intervals=None, submit_partially_completed_forms=False,
            include_case_updates_in_partial_submissions=False):

        now = utcnow()

        session = cls(
            couch_id=uuid.uuid4().hex,
            connection_id=contact.get_id,
            form_xmlns=form.xmlns,
            start_time=now,
            modified_time=now,
            completed=False,
            domain=domain,
            user_id=contact.get_id,
            app_id=app.get_id,
            session_type=XFORMS_SESSION_SMS,
            phone_number=strip_plus(phone_number),
            expire_after=expire_after,
            session_is_open=True,
            reminder_intervals=reminder_intervals or [],
            current_reminder_num=0,
            submit_partially_completed_forms=submit_partially_completed_forms,
            include_case_updates_in_partial_submissions=include_case_updates_in_partial_submissions,
        )

        session.set_current_action_due_timestamp()

        return session

    @classmethod
    def get_contact_id_from_session_id(cls, session_id):
        result = list(cls.objects.filter(session_id=session_id).values_list('connection_id', flat=True))

        if len(result) == 0:
            raise cls.DoesNotExist
        elif len(result) > 1:
            raise cls.MultipleObjectsReturned

        return result[0]

    @property
    def current_action_is_a_reminder(self):
        return self.current_reminder_num < len(self.reminder_intervals)

    def set_current_action_due_timestamp(self):
        if self.expire_after == 0:
            self.end_time = self.start_time
            self.current_action_due = self.start_time
            self.session_is_open = False
            return

        if self.current_action_is_a_reminder:
            minutes_from_beginning = sum(self.reminder_intervals[0:self.current_reminder_num + 1])
            self.current_action_due = self.start_time + timedelta(minutes=minutes_from_beginning)
        else:
            self.current_action_due = self.start_time + timedelta(minutes=self.expire_after)

    def move_to_next_action(self):
        while self.current_action_is_a_reminder and self.current_action_due < utcnow():
            self.current_reminder_num += 1
            self.set_current_action_due_timestamp()

    def get_channel(self):
        return get_channel_for_contact(self.connection_id, self.phone_number)


class XFormsSessionSynchronization:
    """
    This class acts as a container for a set of functions related to
    making sure each Channel(backend_id, phone_number) only has one
    running session at a time.

    Currently the backend_id `None`, which represents our inability to
    find a suitable backend given the configuration, is treated as if it
    were an actual backend in terms of the one-session-per-channel
    semantics, resulting in the behavior that a phone number with a
    broken channel (bad PhoneNumber/backend configuration) can only have
    one running session at a time. In practice this session will fail in
    other ways (since there's no good channel to interact on) but we let
    that fail downstream like it would without the synchronization
    piece. If there seem to be backups of sessions on phone numbers with
    broken channels, it may be worth revisiting the choice to preserve
    one-session-per-channel semantics even for broken channels.
    """

    @classmethod
    def claim_channel_for_session(cls, session):
        """
        This is a non-blocking acquire.

        The session that claims a channel must also release it when it's over.
        Returns True if it was able to claim the channel.
        """
        channel = session.get_channel()
        with cls._critical_section(channel):
            if cls._channel_is_available_for_session(session):
                cls._set_running_session_info_for_channel(
                    channel,
                    RunningSessionInfo(session.session_id, session.connection_id),
                    # We aren't relying on the expiry here to free up the session: we manually release it.
                    # Still, there is no situation where we'd want to keep this longer than that.
                    session.expire_after * 60,
                )
                return True
            else:
                return False

    @classmethod
    def channel_is_available_for_session(cls, session):
        """
        Check if there's another session running on a channel

        Returns
          - True if (1) the channel is unclaimed or (2) the channel is already claimed by this session
          - False if the channel is already claimed by a different session

        A value of True does not guarantee that this session could claim it:
        a subsequent call to claim_channel_for_session could still return False
        i.e. if another session claims it first.
        """
        with cls._critical_section(session.get_channel()):
            return cls._channel_is_available_for_session(session)

    @classmethod
    def _channel_is_available_for_session(cls, session):
        channel = session.get_channel()
        running_session_info = cls.get_running_session_info_for_channel(channel)
        return (
            not running_session_info.session_id
            or cls._clear_stale_channel_claim(channel)
            or running_session_info.session_id == session.session_id
        )

    @classmethod
    def release_channel_for_session(cls, session):
        """
        This allows another session to claim the channel

        The contact_id remains set, and incoming SMS will keep affinity with that contact
        until another session claims the channel.
        """
        channel = session.get_channel()
        with cls._critical_section(channel):
            running_session_info = cls.get_running_session_info_for_channel(channel)
            if cls._channel_is_available_for_session(session):
                cls._release_running_session_info_for_channel(running_session_info, channel)

    @classmethod
    def set_channel_for_affinity(cls, session):
        """
        Set the channel affinity for the session. This is used for manually setting the affinity.

        Returns True if the affinity was set
        """
        channel = session.get_channel()
        with cls._critical_section(channel):
            if cls._channel_is_available_for_session(session):
                session_info = RunningSessionInfo(None, session.connection_id)
                cls._release_running_session_info_for_channel(session_info, channel)
                return True
        return False

    @classmethod
    def clear_stale_channel_claim(cls, channel):
        with cls._critical_section(channel):
            return cls._clear_stale_channel_claim(channel)

    @classmethod
    def _clear_stale_channel_claim(cls, channel):
        running_session_info = cls.get_running_session_info_for_channel(channel)
        if running_session_info.session_id:
            session = SQLXFormsSession.by_session_id(running_session_info.session_id)
            if not (session and session.session_is_open):
                cls._release_running_session_info_for_channel(running_session_info, channel)
                return True
        return False

    @classmethod
    def get_running_session_info_for_channel(cls, channel):
        """
        Returns RunningSessionInfo(session_id, contact_id) for the session currently claiming the channel
        """
        key = cls._channel_affinity_cache_key(channel)
        return cache.get(key) or RunningSessionInfo(None, None)

    @classmethod
    def _set_running_session_info_for_channel(cls, channel, running_session_info, expiry):
        key = cls._channel_affinity_cache_key(channel)
        cache.set(key, running_session_info, expiry)

    @classmethod
    def _release_running_session_info_for_channel(cls, running_session_info, channel):
        # Drop the session_id but keep the contact_id
        # This will let incoming SMS keep affinity with that contact_id until a new session starts
        running_session_info = running_session_info._replace(session_id=None)
        cls._set_running_session_info_for_channel(
            channel, running_session_info,
            # Keep affinity for 30 days
            30 * 24 * 60 * 60
        )

    @staticmethod
    def _channel_affinity_cache_key(channel):
        return f'XFormsSessionSynchronization.value.{channel.backend_id}/{apply_leniency(channel.phone_number)}'

    @staticmethod
    def _critical_section(channel):
        return CriticalSection([
            (
                f'XFormsSessionSynchronization.critical_section.{channel.backend_id}/'
                f'{apply_leniency(channel.phone_number)}'
            )
        ], timeout=5 * 60)


@quickcache(['contact_id', 'phone_number'])
def get_channel_for_contact(contact_id, phone_number):
    """
    For a given contact_id, phone_number pair, look up the gateway to be used and return the result as a Channel

    If a PhoneNumber object does not exist for the pair,
    or attempting to determine the gateway backend results in a BadSMSConfigException
    a channel will be returned with backend_id=None
    """
    backend_id = None
    phone_number_record = PhoneNumber.get_phone_number_for_owner(contact_id, phone_number)
    if phone_number_record:
        phone_number = phone_number_record.phone_number  # prefer this number since it has leniency applied
        try:
            backend = phone_number_record.backend
        except BadSMSConfigException:
            backend = None
        if backend:
            backend_id = backend.couch_id

    return SMSChannel(
        backend_id=backend_id,
        phone_number=phone_number,
    )


RunningSessionInfo = namedtuple('RunningSessionInfo', ['session_id', 'contact_id'])
# A channel is a connection between a gateway on our end an a phone number on the user end
# A single channel can be used by multiple contacts,
# but each channel should only have one active session at a time
SMSChannel = namedtuple('SMSChannel', ['backend_id', 'phone_number'])
