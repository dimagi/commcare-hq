from datetime import datetime
from couchdbkit.ext.django.schema import StringProperty, Document,\
    DateTimeProperty, BooleanProperty, IntegerProperty

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
    
    @classmethod
    def latest_by_session_id(cls, id):
        return XFormsSession.view("smsforms/sessions_by_touchforms_id", 
                                  startkey=[id],
                                  endkey=[id, {}],
                                  include_docs=True).one()
    
        
from . import signals
