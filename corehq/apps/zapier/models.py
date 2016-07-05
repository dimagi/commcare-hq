from django.db import models


class ZapierSubscription(models.Model):
    url = models.URLField(unique=True)
    user_id = models.CharField(max_length=128)
    domain = models.CharField(max_length=128)
    event_name = models.CharField(max_length=128)
    application_id = models.CharField(max_length=128)
    form_xmlns = models.CharField(max_length=128)
    repeater_id = models.CharField(max_length=128)
