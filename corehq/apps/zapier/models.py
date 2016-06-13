import requests
from django.db import models


class Subscription(models.Model):
    url = models.URLField(unique=True)
    user_id = models.CharField(max_length=128)
    domain = models.CharField(max_length=128)
    event_name = models.CharField(max_length=128)
    form_xmlns = models.CharField(max_length=128)

    def send_to_subscriber(self, payload):
        return requests.post(self.url, json=payload)
