from datetime import datetime
from couchdbkit import MultipleResultsFound
from couchforms.models import XFormInstance
from django.db import models
from django.db.models import Q
from django.utils.translation import ugettext_noop


XFORMS_SESSION_SMS = "SMS"
XFORMS_SESSION_IVR = "IVR"
XFORMS_SESSION_TYPES = [XFORMS_SESSION_SMS, XFORMS_SESSION_IVR]


class SQLXFormsSession(models.Model):
    """
    Keeps information about an SMS XForm session.
    """
    # generic properties
    couch_id = models.CharField(db_index=True, max_length=50)
    connection_id = models.CharField(null=True, blank=True, db_index=True, max_length=50)
    session_id = models.CharField(null=True, blank=True, db_index=True, max_length=50)
    form_xmlns = models.CharField(null=True, blank=True, max_length=100)
    start_time = models.DateTimeField()
    modified_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)
    completed = models.BooleanField(default=False)

    # HQ specific properties
    domain = models.CharField(null=True, blank=True, db_index=True, max_length=100)
    user_id = models.CharField(null=True, blank=True, max_length=50)
    app_id = models.CharField(null=True, blank=True, max_length=50)
    submission_id = models.CharField(null=True, blank=True, max_length=50)
    survey_incentive = models.CharField(null=True, blank=True, max_length=100)
    session_type = models.CharField(max_length=10, choices=zip(XFORMS_SESSION_TYPES, XFORMS_SESSION_TYPES),
                                    default=XFORMS_SESSION_SMS)
    workflow = models.CharField(null=True, blank=True, max_length=20)
    reminder_id = models.CharField(null=True, blank=True, max_length=50)

    class Meta:
        app_label = 'smsforms'

    def __unicode__(self):
        return 'Form %(form)s in domain %(domain)s. Last modified: %(mod)s' % \
            {"form": self.form_xmlns,
             "domain": self.domain,
             "mod": self.modified_time}

    @property
    def _id(self):
        return self.couch_id

    def end(self, completed):
        """
        Marks this as ended (by setting end time).
        """
        self.completed = completed
        self.modified_time = self.end_time = datetime.utcnow()

    @property
    def related_subevent(self):
        subevents = self.messagingsubevent_set.all()
        return subevents[0] if subevents else None

    @property
    def status(self):
        xform_instance = None
        if self.submission_id:
            xform_instance = XFormInstance.get(self.submission_id)

        if xform_instance:
            if xform_instance.partial_submission:
                return ugettext_noop('Completed (Partially Completed Submission)')
            else:
                return ugettext_noop('Completed')
        else:
            if self.is_open and self.session_type == XFORMS_SESSION_SMS:
                return ugettext_noop('In Progress')
            else:
                return ugettext_noop('Not Finished')

    @property
    def is_open(self):
        """
        True if this session is still open, False otherwise.
        """
        return self.end_time is None

    @classmethod
    def get_all_open_sms_sessions(cls, domain, contact_id):
        return cls.objects.filter(
            Q(session_type__isnull=True) | Q(session_type=XFORMS_SESSION_SMS),
            domain=domain,
            connection_id=contact_id,
            end_time__isnull=True,
        )

    @classmethod
    def close_all_open_sms_sessions(cls, domain, contact_id):
        sessions = cls.get_all_open_sms_sessions(domain, contact_id)
        for session in sessions:
            session.end(False)
            session.save()

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


def get_session_by_session_id(id):
    return SQLXFormsSession.by_session_id(id)


from . import signals
