from datetime import datetime
from couchdbkit.ext.django.schema import StringProperty, Document,\
    DateTimeProperty, BooleanProperty, IntegerProperty
from dimagi.utils.couch.database import is_bigcouch, bigcouch_quorum_count

XFORMS_SESSION_SMS = "SMS"
XFORMS_SESSION_IVR = "IVR"
XFORMS_SESSION_TYPES = [XFORMS_SESSION_SMS, XFORMS_SESSION_IVR]

class XFormsSession(Document):
    """
    Keeps information about an SMS XForm session. 
    """
    # generic properties
    connection_id = StringProperty()
    session_id = StringProperty()
    form_xmlns = StringProperty()
    start_time = DateTimeProperty()
    modified_time = DateTimeProperty()
    end_time = DateTimeProperty()
    completed = BooleanProperty()
    
    # HQ specific properties
    domain = StringProperty()
    user_id = StringProperty()
    app_id = StringProperty()
    submission_id = StringProperty()
    survey_incentive = StringProperty()
    session_type = StringProperty(choices=XFORMS_SESSION_TYPES, default=XFORMS_SESSION_SMS)
    workflow = StringProperty() # One of the corehq.apps.sms.models.WORKFLOW_* constants describing what kind of workflow this session was a part of
    reminder_id = StringProperty() # Points to the _id of an instance of corehq.apps.reminders.models.CaseReminder that this session is tied to
    
    def save(self, *args, **kwargs):
        if is_bigcouch() and "w" not in kwargs:
            # Force a write to all nodes before returning
            kwargs["w"] = bigcouch_quorum_count()
        return super(XFormsSession, self).save(*args, **kwargs)
    
    def __unicode__(self):
        return 'Form %(form)s in domain %(domain)s. Last modified: %(mod)s' % \
            {"form": self.form_xmlns, 
             "domain": self.domain, 
             "mod": self.modified_time}
    
    def end(self, completed):
        """
        Marks this as ended (by setting end time).
        """
        self.completed = completed
        self.modified_time = self.end_time = datetime.utcnow()

    @property
    def is_open(self):
        """
        True if this session is still open, False otherwise.
        """
        return self.end_time is None

    @classmethod
    def get_all_open_sms_sessions(cls, domain, contact_id):
        sessions = cls.view("smsforms/open_sms_sessions_by_connection",
                            key=[domain, contact_id],
                            include_docs=True).all()
        return sessions

    @classmethod
    def close_all_open_sms_sessions(cls, domain, contact_id):
        sessions = cls.get_all_open_sms_sessions(domain, contact_id)
        for session in sessions:
            session.end(False)
            session.save()

    @classmethod
    def by_session_id(cls, id):
        return XFormsSession.view("smsforms/sessions_by_touchforms_id",
                                  key=id, include_docs=True).one()

    @classmethod
    def get_open_sms_session(cls, domain, contact_id):
        """
        Looks up the open sms survey session for the given domain and contact_id.
        Only one session is expected to be open at a time.
        Raises MultipleResultsFound if more than one session is open.
        """
        session = cls.view("smsforms/open_sms_sessions_by_connection",
                           key=[domain, contact_id],
                           include_docs=True).one()
        return session

from . import signals
