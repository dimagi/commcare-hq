from datetime import datetime
from couchdbkit.ext.django.schema import StringProperty, Document,\
    DateTimeProperty, BooleanProperty, IntegerProperty

class XFormsSession(Document):
    """
    Keeps information about an SMS XForm session. 
    """
    # generic properties
    connection_id = StringProperty()
    session_id = IntegerProperty()
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
        
        
from . import signals