import jsonfield
from django.db import models
from django.utils.translation import gettext as _

from corehq.motech.models import ConnectionSettings


class UserDataStore(object):
    CUSTOM_USER_DATA = 'custom_user_data'
    USER_CASE = 'user_case'
    OTHER_CASE_TYPE = 'other_case_type'
    CHOICES = [
        (CUSTOM_USER_DATA, _('Custom User Data')),
        (USER_CASE, _('User Case')),
        (OTHER_CASE_TYPE, _('Other Case Type')),
    ]


class KycConfig(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    user_data_store = models.CharField(max_length=25, choices=UserDataStore.CHOICES)
    other_case_type = models.CharField(max_length=126, null=True)
    api_field_to_user_data_map = jsonfield.JSONField(default=dict)
    connection_settings = models.ForeignKey(ConnectionSettings, on_delete=models.PROTECT)
