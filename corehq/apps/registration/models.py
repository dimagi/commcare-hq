from couchdbkit.ext.django.schema import Document, StringProperty,\
    BooleanProperty, DateTimeProperty, IntegerProperty
import datetime

class RegistrationRequest(Document):
    tos_confirmed = BooleanProperty(default=False)
    request_time = DateTimeProperty()
    request_ip = StringProperty()
    activation_guid = StringProperty()
    confirm_time = DateTimeProperty()
    confirm_ip = StringProperty()
    domain = StringProperty()
    new_user_username = StringProperty()
    requesting_user_username = StringProperty()

    @classmethod
    def get_by_guid(cls, guid):
        result = cls.view("registration/requests_by_guid",
            key=guid,
            reduce=False,
            include_docs=True).first()
        return result

    @classmethod
    def get_requests_today(cls):
        today = datetime.datetime.utcnow()
        yesterday = today - datetime.timedelta(1)
        result = cls.view("registration/requests_by_time",
            startkey=yesterday.isoformat(),
            endkey=today.isoformat(),
            reduce=True).all()
        if not result:
            return 0
        return result[0]['value']

    @classmethod
    def get_request_for_username(cls, username):
        result = cls.view("registration/requests_by_username",
            key=username,
            reduce=False,
            include_docs=True).first()
        return result
