from copy import copy
from datetime import datetime
from couchdbkit import MultipleResultsFound
from couchdbkit.ext.django.schema import StringProperty, Document,\
    DateTimeProperty, BooleanProperty
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from dimagi.utils.couch.database import is_bigcouch, bigcouch_quorum_count
from dimagi.utils.logging import notify_error

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
        super(XFormsSession, self).save(*args, **kwargs)
        sync_sql_session_from_couch_session(self)

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
        return cls.view("smsforms/sessions_by_touchforms_id",
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

    do_not_sync = False  # used in the syncing code, can be deleted when couch model is removed

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


SESSION_PROPERTIES_TO_SYNC = [
    'connection_id',
    'session_id',
    'form_xmlns',
    'start_time',
    'modified_time',
    'end_time',
    'completed',
    'domain',
    'user_id',
    'app_id',
    'submission_id',
    'survey_incentive',
    'session_type',
    'workflow',
    'reminder_id',
]


def sync_sql_session_from_couch_session(couch_session):
    data = copy(couch_session._doc)
    couch_id = data.pop('_id')
    data.pop('_rev', None)
    try:
        sql_session = SQLXFormsSession.objects.get(couch_id=couch_id)
    except SQLXFormsSession.DoesNotExist:
        sql_session = SQLXFormsSession(couch_id=couch_id)

    for attr in SESSION_PROPERTIES_TO_SYNC:
        setattr(sql_session, attr, data.get(attr, None))

    # hack to avoid excess saves. see sync_couch_session_from_sql_session
    sql_session.do_not_sync = True
    sql_session.save()
    sql_session.do_not_sync = False


@receiver(post_save, sender=SQLXFormsSession)
def sync_signal_catcher(sender, instance, *args, **kwargs):
    sync_couch_session_from_sql_session(instance)


def sync_couch_session_from_sql_session(sql_session):
    if sql_session.do_not_sync:
        return

    if not sql_session.couch_id:
        notify_error('Only existing sessions can be synced for now. sql session id is {}'.format(sql_session.pk))
        return

    couch_doc = XFormsSession.get(sql_session.couch_id)
    for attr in SESSION_PROPERTIES_TO_SYNC:
        setattr(couch_doc, attr, getattr(sql_session, attr))

    # don't call .save() since that will create a recursive loop of syncing
    XFormsSession.get_db().save_doc(couch_doc._doc)


from . import signals
