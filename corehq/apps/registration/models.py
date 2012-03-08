from couchdbkit.ext.django.schema import Document, StringProperty,\
    BooleanProperty, DateTimeProperty, IntegerProperty
import datetime
from django.db import models
from django.contrib.auth.models import User
from corehq.apps.domain.models import OldDomain

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



class OldRegistrationRequest(models.Model):
    tos_confirmed = models.BooleanField(default=False)
    # No verbose name on times and IPs - filled in on server
    request_time = models.DateTimeField()
    request_ip = models.IPAddressField()
    activation_guid = models.CharField(max_length=32, unique=True)
    # confirm info is blank until a confirming click is received
    confirm_time = models.DateTimeField(null=True, blank=True)
    confirm_ip = models.IPAddressField(null=True, blank=True)
    domain = models.OneToOneField(OldDomain)
    new_user = models.ForeignKey(User, related_name='new_user') # Not clear if we'll always create a new user - might be many reqs to one user, thus FK
    # requesting_user is only filled in if a logged-in user requests a domain.
    requesting_user = models.ForeignKey(User, related_name='requesting_user', null=True, blank=True) # blank and null -> FK is optional.

    class Meta:
        db_table = 'domain_registration_request'

# To be added:
# language
# number pref
# currency pref
# date pref
# time pref
