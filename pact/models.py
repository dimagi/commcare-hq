import uuid

def make_uuid():
    return uuid.uuid4().hex

#placeholder for management of pact case models
from datetime import datetime
from couchdbkit.ext.django.schema import StringProperty, DateTimeProperty, BooleanProperty, Document


class CDotWeeklySchedule(Document):
    """Weekly schedule where each day has a username"""
    schedule_id = StringProperty(default=make_uuid)

    sunday = StringProperty()
    monday = StringProperty()
    tuesday = StringProperty()
    wednesday = StringProperty()
    thursday = StringProperty()
    friday = StringProperty()
    saturday = StringProperty()


    comment = StringProperty()

    deprecated = BooleanProperty(default=False)

    started = DateTimeProperty(default=datetime.utcnow, required=True)
    ended = DateTimeProperty()

    created_by = StringProperty() #userid
    edited_by = StringProperty() #userid

    class Meta:
        app_label='pactpatient'
