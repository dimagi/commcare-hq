from datetime import datetime
from django.db import models

from django.contrib.auth.models import User


class GoogleApiToken(models.Model):
    user = models.ForeignKey(User, related_name='google_api_tokens', on_delete=models.CASCADE)
    token = models.CharField(max_length=700)
    date_created = models.DateField(auto_now_add=True)


class LiveGoogleSheetSchedule(models.Model):
    export_config_id = models.CharField(max_length=250, db_index=True)
    is_active = models.BooleanField(default=True)
    start_time = models.IntegerField(default=200)
    google_sheet_id = models.CharField(max_length=250)

    def start_refresh(self):
        self.status = LiveGoogleSheetRefreshStatus.objects.create(
            schedule=self,
            date_start=datetime.utcnow()
        )

    def stop_refresh(self, error_reason=None, error_note=None):
        self.status.date_end = datetime.utcnow()
        self.status.refresh_error_reason = error_reason
        self.status.refresh_error_note = error_note
        self.status.save()

    def is_currently_refreshing(self):
        return LiveGoogleSheetRefreshStatus.objects.filter(
            schedule=self,
            date_end=None
        ).exists()


class LiveGoogleSheetErrorReason():
    NO_ERROR = None
    INVALID_TOKEN = 'token'
    TIMEOUT = 'timeout'
    OTHER = 'other'

    CHOICES = (
        (NO_ERROR, "No Error"),
        (INVALID_TOKEN, "Invalid Token"),
        (TIMEOUT, "Data Timeout"),
        (OTHER, "Other..."),
    )


class LiveGoogleSheetRefreshStatus(models.Model):
    schedule = models.ForeignKey(LiveGoogleSheetSchedule, on_delete=models.CASCADE)
    date_start = models.DateTimeField(auto_now_add=True)
    date_end = models.DateTimeField(null=True, blank=True)
    refresh_error_reason = models.CharField(
        max_length=16,
        choices=LiveGoogleSheetErrorReason.CHOICES,
        null=True,
        default=LiveGoogleSheetErrorReason.NO_ERROR,
    )
    refresh_error_note = models.TextField(null=True, blank=True)
