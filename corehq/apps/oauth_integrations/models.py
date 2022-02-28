from django.db import models

from django.contrib.auth.models import User
from django.forms import CharField


class GoogleApiToken(models.Model):
    user = models.ForeignKey(User, related_name='google_api_tokens', on_delete=models.CASCADE)
    token = models.CharField(max_length=700)
    date_created = models.DateField(auto_now_add=True)


class LiveGoogleSheetSchedule(models.Model):
    export_config_id = models.CharField(length=250, db_index=True)
    is_active = models.BooleanField(default=True)
    start_time = models.IntegerField(default=200)
    google_sheet_id = CharField(length=250)
